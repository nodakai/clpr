# Expression Syntax Specification

This document formally defines the expression language used for filtering numeric and string fields in AWS pricing queries.

## Overview

The expression parser supports:
- Comparison operators: `>`, `<`, `>=`, `<=`, `=`, `!=`
- Range operator: `..` (inclusive)
- Logical operators: `&&` (AND), `||` (OR), `!` (NOT)
- String methods: `starts_with()`, `ends_with()`, `has()`
- Parenthetical grouping

**Target fields:** `vcpu`, `memory_gb`, `price_hourly_min`, `price_hourly_max`, and `instance_type` (with method calls).

## Formal Grammar (EBNF)

```
expression     ::= logical_or

logical_or     ::= logical_and ( '||' logical_and )*
logical_and    ::= unary ( '&&' unary )*
unary          ::= '!' unary | primary
primary        ::= number_range
                | comparison
                | '(' expression ')'

number_range   ::= NUMBER '..' NUMBER
comparison     ::= comp_operator value
comp_operator  ::= '>=' | '<=' | '>' | '<' | '=' | '!='
value          ::= NUMBER | STRING | IDENTIFIER

NUMBER         ::= [0-9]+ ('.' [0-9]+)?
STRING         ::= '"' [^"]* '"' | "'" [^']* "'"
IDENTIFIER     ::= [a-zA-Z_][a-zA-Z0-9_]*
```

## Tokenization

The lexer produces the following token types:

| Token Type | Values | Description |
|------------|--------|-------------|
| `NUMBER` | `42`, `3.14` | Decimal number (float or int) |
| `STRING` | `"hello"` | Quoted string (single or double quotes) |
| `OPERATOR` | `>`, `<`, `>=`, `<=`, `=`, `!=` | Comparison operators |
| `RANGE` | `..` | Range operator (two consecutive dots) |
| `LOGICAL` | `&&`, `||` | Logical AND/OR |
| `LPAREN` | `(` | Left parenthesis |
| `RPAREN` | `)` | Right parenthesis |
| `METHOD` | `starts_with`, `ends_with`, `has` | String method calls |
| `COMMA` | `,` | Argument separator (in method calls) |
| `IDENTIFIER` | `field_name` | Unquoted identifier (field name only) |
| `EOF` | (end) | End of input |

**Whitespace:** Ignored between tokens. Expressions `4..8` and `4 .. 8` are **not** both valid - the range operator must be contiguous (`..`).

## Operator Precedence

From highest to lowest:

1. **`!`** (unary NOT)
2. **Comparison operators** (`>`, `<`, `>=`, `<=`, `=`, `!=`) and **range** (`..`)
3. **`&&`** (AND)
4. **`||`** (OR)

Parentheses `()` override default precedence.

**Example:**
```
!a > 5 && b < 10
```
Parsed as:
```
((!a) > 5) && (b < 10)
```
Not:
```
!(a > 5 && b < 10)
```
Use parentheses for explicit grouping:
```
!(a > 5 && b < 10)
```

## Numeric Expressions

Numeric fields (`vcpu`, `memory_gb`, price fields) support:

### Simple Comparisons
```
vcpu >= 4
memory_gb < 32
hourly = 0.096
```

### Inclusive Ranges
```
4..8        → vcpu >= 4 AND vcpu <= 8
0.5..4.0    → memory_gb >= 0.5 AND memory_gb <= 4.0
```

**Important:** Range is inclusive on both ends. `4..8` matches 4, 5, 6, 7, and 8.

### Negation
```
!vcpu < 4    → vcpu >= 4
!4..8        → vcpu < 4 OR vcpu > 8
```

**Note:** `!4..8` expands to `NOT (vcpu >= 4 AND vcpu <= 8)`, which is equivalent to `vcpu < 4 OR vcpu > 8`.

### Complex Grouping
```
(vcpu >= 4 && vcpu <= 8) || (vcpu >= 16)
```

## String Methods

For string fields (`instance_type`), the parser detects method calls directly in the filter value.

### Supported Methods

| Method | SQL Translation | Example |
|--------|-----------------|---------|
| `starts_with("prefix")` | `field LIKE 'prefix%'` | `starts_with("m5.")` → `instance_type LIKE 'm5.%'` |
| `ends_with("suffix")` | `field LIKE '%suffix'` | `ends_with("xlarge")` → `instance_type LIKE '%xlarge'` |
| `has("substring")` | `field LIKE '%substring%'` | `has("2xlarge")` → `instance_type LIKE '%2xlarge%'` |

**Method call syntax:**
- Method name followed immediately by `(`
- Single argument: quoted string (single or double quotes allowed)
- No commas, multiple arguments, or function calls supported
- Quotes are stripped before building LIKE pattern

Examples:
```
instance_type: starts_with("c5.")
instance_type: ends_with('large')
```

**Wildcard Alternative:**

Using `*` in a plain string also translates to `LIKE`:
```
instance_type: m5.*large    → instance_type LIKE 'm5.%large'
instance_type: *2xlarge*    → instance_type LIKE '%2xlarge%'
```

This is legacy syntax; prefer explicit methods.

## Type System

### Numbers
- Parsed as JavaScript `parseFloat()`
- Integers and floats both accepted
- Stored as double-precision floating point
- Comparisons use numeric ordering (lexicographic string ordering not supported)

### Strings
- Must be quoted with `"` or `'`
- Escape sequences: `\"`, `\'`, `\\` supported
- No interpolation or variable expansion
- Case-sensitive comparisons

### Booleans
Not directly supported in expressions. Logical operators produce boolean results but boolean values cannot be literals.

## Edge Cases

### Whitespace
- Ignored everywhere except within quoted strings
- `4..8` works, `4 .. 8` fails (range operator must be contiguous)
- `>= 4` works (space after operator allowed)

### Quoted Strings
- Single and double quotes both accepted
- Must match: `"hello'` fails
- Escape with backslash: `"He said \"hello\""` → `He said "hello"`
- Backslash before quote: `"C:\\Path"` → `C:\Path`

### Parentheses
- Must be balanced: `(>=4 && <=8)` valid; `(>=4 && <=8` invalid
- Unbalanced parentheses throw error with position

### Error Reporting
Syntax errors include character position:
```
Error parsing expression for field "vcpu": Unexpected token at position 5: '&&'
```
Positions are zero-indexed within the expression string.

### Empty Expressions
Empty string `""` is valid and produces no conditions. The caller (`buildWhereClause`) uses `'1=1'` as fallback.

### Nil/Null Values
Not supported. All values in expressions must be numbers or quoted strings.

### Method Arguments
Only single string literal arguments allowed:
- Valid: `starts_with("prefix")`
- Invalid: `starts_with(prefix)`
- Invalid: `starts_with("a", "b")`
- Invalid: `starts_with(123)`

## Integration with UI

### Filter Components

Each filter component emits values that `buildWhereClause` interprets:

| Component | Field | Output Type | Parser Used |
|-----------|-------|-------------|-------------|
| RangeFilter | `vcpu`, `memory_gb` | string expression | `parseExpression(field, value)` |
| PriceFilter | `price_hourly_min`, `price_hourly_max` | number (direct) | None (bound parameters) |
| InstanceTypeFilter | `instance_type` | string with method/wildcard | `parseStringMethod()` or LIKE |
| SelectFilter | `region`, `os`, `tenancy` | string or string[] | IN clause (no parser) |
| MultiSelectFilter | `storage_type`, `purchase_option` | string[] | IN clause (no parser) |

### Expression Processing Flow

1. User types into `RangeFilter` (e.g., `>=4 && <=8`)
2. `buildWhereClause` calls `parseExpression('vcpu', '>=4 && <=8')`
3. Parser tokenizes, builds AST, returns `{ sql: "(vcpu >= ? AND vcpu <= ?)", params: [4, 8] }`
4. Conditions array accumulates; all joined with `AND`
5. Final WHERE: `"vcpu >= ? AND vcpu <= ? AND os IN (?)"` with bound params

### Error Handling

- Parsing errors are caught and logged: `console.warn('Failed to parse vcpu expression:', e)`
- Failed expressions are silently skipped (no WHERE condition added)
- User sees no error unless debug mode enabled
- This allows partial filter results when some expressions are malformed

**Implementation:** See `frontend/src/query-builder.ts` for full parser implementation.

## Sample Expressions

### Simple Ranges
```
4..8
16..
..32       (not directly supported; use <=32)
```

### Complex Logic
```
(vcpu >= 4 && vcpu <= 8) || (vcpu >= 16)
!(vcpu < 4 || memory_gb < 8)
```

### Instance Type Patterns
```
starts_with("m5.")
ends_with("2xlarge")
has("xlarge") && !has("nano")
```

### Real-World Examples

**Cost-optimized general purpose:**
```
service = "ec2" && vcpu >= 4 && vcpu <= 8 && os = "Linux" && starts_with("m5.")
```

**Memory-optimized with discount:**
```
memory_gb >= 64 && purchase_option = "Reserved" && lease_term = "1yr"
```

**Windows instances excluding tiny ones:**
```
os = "Windows" && vcpu >= 2 && !instance_type.includes("nano")  // using !has("nano")
```

## Limitations

- **Maximum expression length:** Not enforced, but very long expressions (>1000 chars) may impact performance
- **Nesting depth:** Limited by JavaScript call stack (theoretical limit ~10k nested parentheses, practical ~100)
- **Parameter count:** SQLite has 999 parameter limit per query. Multiple fields with multiple range clauses can exceed this (unlikely with current filters)
- **No arithmetic:** Cannot compute `vcpu * 2` or `hourly * 24 * 30` (use precomputed `monthly` column)
- **No functions:** No mathematical functions (sin, log, etc.)
- **No string concatenation:** LIKE patterns built by methods only
- **No case-insensitive matching:** All string comparisons are case-sensitive (use known AWS capitalization)
- **No regex:** Only simple `LIKE` patterns via methods

## Future Extensions

Potential additions (not implemented):
- `IN` operator for numbers: `vcpu IN (2, 4, 8, 16)`
- Ternary conditional: `? :`
- Arithmetic expressions: `vcpu >= 4 * 2`
- Date functions: comparing against `effective_date`
- Case-insensitive flag: `ilike()` or `~*` regex

---

*Reference Implementation:* `frontend/src/query-builder.ts`
