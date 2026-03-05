import sys
import re

filepath = 'frontend/src/query-builder.ts'
with open(filepath, 'r') as f:
    content = f.read()

# 1. Fix range parentheses: change `(${field} >= ? AND ${field} <= ?)` to `${field} >= ? AND ${field} <= ?`
content = re.sub(
    r'`\(\$\{field\} >= \? AND \$\{field\} <= \?\)`',
    '`${field} >= ? AND ${field} <= ?`',
    content
)

# 2. Fix tokenizer for negative numbers
# Find the numberMatch block and insert preceding logic for unary minus.
# We'll replace the section from "const numberMatch = expr.slice(pos).match" onward to include a preceding check.
old_tokenizer_part = r'''    const numberMatch = expr.slice\(pos\)\.match/^\(\\d\+\\.\\d\+\)\?/)/
    if \(numberMatch\) {
      tokens\.push\(\\{ type: 'NUMBER', value: numberMatch\[1\], position: pos \\}\);
      pos \+= numberMatch\[0\]\.length;
      continue;
    }'''

new_tokenizer_part = r'''    // Handle negative numbers: '-' followed by digits when after operator or start
    if (char === '-') {
      const rest = expr.slice(pos + 1);
      const digitMatch = rest.match(/^\\d+(\\.\\d+)?/);
      if (digitMatch) {
        const prev = tokens.length > 0 ? tokens[tokens.length - 1] : null;
        const allowed = prev ? ['OPERATOR', 'LOGICAL', 'LPAREN', 'RANGE'].includes(prev.type) : true;
        if (allowed) {
          tokens.push({ type: 'NUMBER', value: '-' + digitMatch[0], position: pos });
          pos += 1 + digitMatch[0].length;
          continue;
        }
      }
    }

    const numberMatch = expr.slice(pos).match(/^(\\d+(\\.\\d+)?)/);
    if (numberMatch) {
      tokens.push({ type: 'NUMBER', value: numberMatch[1], position: pos });
      pos += numberMatch[0].length;
      continue;
    }'''

# Since regex replacement with multiline is tricky, we'll do a string replace of a marker pattern.
# We'll search for the specific block starting with "const numberMatch = expr.slice(pos).match" and replace preceding lines.
# Simpler: locate that line and insert the negative number handling before it.

lines = content.split('\n')
new_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    # If this line is the numberMatch line, insert negative number handling before it.
    if re.match(r'\s*const numberMatch = expr\.slice\(pos\)\.match\(/\\\^\(\\\\d\+\(\\\\\.\\\\d\+\)\?\)/', line):
        # Insert negative handling before this line.
        indent = re.match(r'^(\s*)', line).group(1)
        new_lines.append(indent + '// Handle negative numbers: \'-\' followed by digits when after operator or start')
        new_lines.append(indent + 'if (char === \'-\') {')
        new_lines.append(indent + '  const rest = expr.slice(pos + 1);')
        new_lines.append(indent + '  const digitMatch = rest.match(/^\\d+(\\.\\d+)?/);')
        new_lines.append(indent + '  if (digitMatch) {')
        new_lines.append(indent + '    const prev = tokens.length > 0 ? tokens[tokens.length - 1] : null;')
        new_lines.append(indent + '    const allowed = prev ? [\'OPERATOR\', \'LOGICAL\', \'LPAREN\', \'RANGE\'].includes(prev.type) : true;')
        new_lines.append(indent + '    if (allowed) {')
        new_lines.append(indent + '      tokens.push({ type: \'NUMBER\', value: \'-\' + digitMatch[0], position: pos });')
        new_lines.append(indent + '      pos += 1 + digitMatch[0].length;')
        new_lines.append(indent + '      continue;')
        new_lines.append(indent + '    }')
        new_lines.append(indent + '  }')
        new_lines.append(indent + '}')
        # Also need to modify original line to use regex without negative
        new_lines.append(indent + 'const numberMatch = expr.slice(pos).match(/^(\\d+(\\.\\d+)?)/);')
        i += 1
        continue
    else:
        new_lines.append(line)
    i += 1

content = '\n'.join(new_lines)

# 3. Add dynamic unknown field handling in buildWhereClause.
# Find the line handling instance_type and after its closing } (catch block), we'll add fallback before the function returns.
# Actually we want to add after all known fields processing, before return. Where is return?
# Search for "const where = conditions.length > 0 ?"
# Insert before that line: code to process any remaining keys.
return_line_idx = None
for i, line in enumerate(lines):
    if re.match(r'\s*const where = conditions\.length > 0', line):
        return_line_idx = i
        break
if return_line_idx is not None:
    # Insert before return line.
    # Determine indent level
    indent_match = re.match(r'^(\s*)', lines[return_line_idx])
    indent = indent_match.group(1) if indent_match else ''
    fallback_code = [
        indent + '// Process any unknown/dynamic filter fields as expressions',
        indent + 'const knownFields = new Set([...simpleFields, ...arrayFields, \'vcpu\', \'memory_gb\', \'price_hourly_min\', \'price_hourly_max\', \'instance_type\']);',
        indent + 'for (const key of Object.keys(filters) as Array<keyof Filters>) {',
        indent + '  if (!knownFields.has(key) && filters[key]) {',
        indent + '    try {',
        indent + '      const result = parseExpression(key, String(filters[key]));',
        indent + '      conditions.push(result.sql);',
        indent + '      params.push(...result.params);',
        indent + '    } catch (e) {',
        indent + '      if (env.DEV) console.warn(\'Failed to parse dynamic field\', key, e);',
        indent + '    }',
        indent + '  }',
        indent + '}',
        ''
    ]
    lines = lines[:return_line_idx] + fallback_code + lines[return_line_idx:]
    content = '\n'.join(lines)

# Write back
with open(filepath, 'w') as f:
    f.write(content)

print('query-builder.ts patched')
