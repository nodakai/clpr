import re

filepath = 'frontend/src/query-builder.ts'
with open(filepath, 'r') as f:
    content = f.read()

# Find the entire buildWhereClause function from its declaration to the closing brace before parseExpression.
# Use regex to match: export function buildWhereClause([\s\S]*?)^\s*}\n(?=\s*export function parseExpression)
pattern = r'(export function buildWhereClause\(filters: Filters\): \{[^}]*\}[^}]*\})(?=\s*export function parseExpression)'
# Actually better to find from "export function buildWhereClause" up to the closing brace and newline before "export function parseExpression"

start_marker = 'export function buildWhereClause(filters: Filters): {'
end_marker = '\n}\n\nexport function parseExpression'
start_idx = content.find(start_marker)
end_idx = content.find(end_marker, start_idx)
if start_idx == -1 or end_idx == -1:
    print('Could not find markers')
    exit(1)

new_function = '''export function buildWhereClause(filters: Filters): { where: string; params: any[] } {
  const conditions: string[] = [];
  const params: any[] = {};

  const simpleSet = new Set<keyof Filters>(['service', 'family']);
  const arraySet = new Set<keyof Filters>(['region', 'storage_type', 'os', 'tenancy', 'purchase_option']);
  const expressionSet = new Set<keyof Filters>(['vcpu', 'memory_gb']);
  const priceMinSet = new Set<keyof Filters>(['price_hourly_min']);
  const priceMaxSet = new Set<keyof Filters>(['price_hourly_max']);

  for (const key of Object.keys(filters) as Array<keyof Filters>) {
    const value = filters[key];
    if (value === undefined || value === null || value === '') continue;

    if (simpleSet.has(key)) {
      conditions.push(`${key} = ?`);
      params.push(value);
    } else if (arraySet.has(key)) {
      const values = Array.isArray(value) ? value : [value];
      if (values.length > 0) {
        const placeholders = values.map(() => '?').join(', ');
        conditions.push(`${key} IN (${placeholders})`);
        params.push(...values);
      }
    } else if (expressionSet.has(key)) {
      try {
        const result = parseExpression(key, String(value));
        conditions.push(result.sql);
        params.push(...result.params);
      } catch (e) {
        if (env.DEV) console.warn('Failed to parse expression for', key, e);
      }
    } else if (priceMinSet.has(key)) {
      conditions.push('hourly >= ?');
      params.push(value as number);
    } else if (priceMaxSet.has(key)) {
      conditions.push('hourly <= ?');
      params.push(value as number);
    } else if (key === 'instance_type') {
      const instanceType = String(value).trim();
      if (instanceType.startsWith('starts_with(') || instanceType.startsWith('ends_with(') || instanceType.startsWith('has(')) {
        try {
          const methodEnd = instanceType.indexOf('(');
          const method = instanceType.substring(0, methodEnd) as StringMethod;
          const argStart = methodEnd + 1;
          const argEnd = instanceType.lastIndexOf(')');
          const arg = instanceType.substring(argStart, argEnd).replace(/^["']|["']$/g, '');
          const result = parseStringMethod('instance_type', method, arg);
          conditions.push(result.sql);
          params.push(...result.params);
        } catch (e) {
          if (env.DEV) console.warn('Failed to parse instance_type method:', e);
          conditions.push('instance_type = ?');
          params.push(value);
        }
      } else {
        if (instanceType.includes('*')) {
          const pattern = instanceType.replace(/*g*/ '*', '%');
          conditions.push('instance_type LIKE ?');
          params.push(pattern);
        } else {
          conditions.push('instance_type = ?');
          params.push(value);
        }
      }
    } else {
      // Unknown field: try as expression
      try {
        const result = parseExpression(key, String(value));
        conditions.push(result.sql);
        params.push(...result.params);
      } catch (e) {
        if (env.DEV) console.warn('Failed to parse dynamic field', key, e);
      }
    }
  }

  const where = conditions.length > 0 ? conditions.join(' AND ') : '1=1';
  return { where, params };
}

'''

# Replace the old function with new
new_content = content[:start_idx] + new_function + content[end_idx:]

with open(filepath, 'w') as f:
    f.write(new_content)

print('buildWhereClause replaced')
