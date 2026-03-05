import env from './env';

type FilterOperator = '=' | '!=' | '>' | '>=' | '<' | '<=';
type LogicalOp = '&&' | '||';
type StringMethod = 'starts_with' | 'ends_with' | 'has';

interface FilterExpression {
  field: string;
  operator?: FilterOperator;
  value: any;
  logicalOp?: LogicalOp;
  rangeTo?: any;
}

interface Filters {
  service?: string;
  region?: string | string[];
  instance_type?: string;
  family?: string;
  vcpu?: string;
  memory_gb?: string;
  storage_type?: string | string[];
  os?: string | string[];
  tenancy?: string | string[];
  purchase_option?: string | string[];
  price_hourly_min?: number;
  price_hourly_max?: number;
}

interface ParsedExpression {
  sql: string;
  params: any[];
}

interface Token {
  type: 'NUMBER' | 'STRING' | 'OPERATOR' | 'LOGICAL' | 'LPAREN' | 'RPAREN' | 'RANGE' | 'METHOD' | 'COMMA' | 'IDENTIFIER' | 'EOF';
  value: string;
  position: number;
}

function tokenize(expr: string): Token[] {
  const tokens: Token[] = [];
  let pos = 0;

  while (pos < expr.length) {
    const char = expr[pos];

    if (/\s/.test(char)) {
      pos++;
      continue;
    }

    if (char === '(') {
      tokens.push({ type: 'LPAREN', value: '(', position: pos });
      pos++;
      continue;
    }
    if (char === ')') {
      tokens.push({ type: 'RPAREN', value: ')', position: pos });
      pos++;
      continue;
    }

    if (char === '.' && expr[pos + 1] === '.') {
      tokens.push({ type: 'RANGE', value: '..', position: pos });
      pos += 2;
      continue;
    }

    // Check unary minus BEFORE operators to handle negative numbers properly
    if (char === '-') {
      const rest = expr.slice(pos + 1);
      const digitMatch = rest.match(/^\d+(\.\d+)?/);
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

    if (char === '&' && expr[pos + 1] === '&') {
      tokens.push({ type: 'LOGICAL', value: '&&', position: pos });
      pos += 2;
      continue;
    }
    if (char === '|' && expr[pos + 1] === '|') {
      tokens.push({ type: 'LOGICAL', value: '||', position: pos });
      pos += 2;
      continue;
    }

    const twoCharOps = ['>=', '<=', '!='];
    if (twoCharOps.includes(expr.slice(pos, pos + 2))) {
      tokens.push({ type: 'OPERATOR', value: expr.slice(pos, pos + 2), position: pos });
      pos += 2;
      continue;
    }
    const oneCharOps = ['>', '<', '='];
    if (oneCharOps.includes(char)) {
      tokens.push({ type: 'OPERATOR', value: char, position: pos });
      pos++;
      continue;
    }

    if (char === '!') {
      tokens.push({ type: 'OPERATOR', value: '!', position: pos });
      pos++;
      continue;
    }

    // Method detection with '(' consumption
    let methodHandled = false;
    const methodNames: StringMethod[] = ['starts_with', 'ends_with', 'has'];
    for (const method of methodNames) {
      if (expr.slice(pos).startsWith(method + '(')) {
        tokens.push({ type: 'METHOD', value: method, position: pos });
        pos += method.length;
        // Consume the opening '('
        if (pos < expr.length && expr[pos] === '(') {
          pos++;
        }
        methodHandled = true;
        break;
      }
    }
    if (methodHandled) continue;

    if (char === '"' || char === "'") {
      const quote = char;
      let value = '';
      pos++;
      while (pos < expr.length && expr[pos] !== quote) {
        if (expr[pos] === '\\' && pos + 1 < expr.length) {
          value += expr[pos + 1];
          pos += 2;
        } else {
          value += expr[pos];
          pos++;
        }
      }
      pos++;
      tokens.push({ type: 'STRING', value, position: pos - value.length - 1 });
      continue;
    }

    const numberMatch = expr.slice(pos).match(/^(\d+(\.\d+)?)/);
    if (numberMatch) {
      tokens.push({ type: 'NUMBER', value: numberMatch[1], position: pos });
      pos += numberMatch[0].length;
      continue;
    }

    if (/[a-zA-Z_][a-zA-Z0-9_]*/.test(char)) {
      let value = '';
      while (pos < expr.length && /[a-zA-Z0-9_]/.test(expr[pos])) {
        value += expr[pos];
        pos++;
      }
      tokens.push({ type: 'IDENTIFIER', value, position: pos - value.length });
      continue;
    }

    if (char === ',') {
      tokens.push({ type: 'COMMA', value: ',', position: pos });
      pos++;
      continue;
    }

    pos++;
  }

  tokens.push({ type: 'EOF', value: '', position: pos });
  return tokens;
}

class ExpressionParser {
  private tokens: Token[];
  private pos: number = 0;

  constructor(tokens: Token[]) {
    this.tokens = tokens;
  }

  private get peek(): Token {
    return this.tokens[this.pos];
  }

  advance(): Token {
    return this.tokens[this.pos++];
  }

  parse(field: string): ParsedExpression {
    const result = this.parseOr(field);
    if (this.peek.type !== 'EOF') {
      throw new Error(`Unexpected token after expression at position ${this.peek.position}`);
    }
    return result;
  }

  private parseOr(field: string): ParsedExpression {
    let left = this.parseAnd(field);

    while (this.peek.type === 'LOGICAL' && this.peek.value === '||') {
      this.advance();
      const right = this.parseAnd(field);
      left = {
        sql: `(${left.sql} OR ${right.sql})`,
        params: [...left.params, ...right.params]
      };
    }

    return left;
  }

  private parseAnd(field: string): ParsedExpression {
    let left = this.parseUnary(field);

    while (this.peek.type === 'LOGICAL' && this.peek.value === '&&') {
      this.advance();
      const right = this.parseUnary(field);
      left = {
        sql: `(${left.sql} AND ${right.sql})`,
        params: [...left.params, ...right.params]
      };
    }

    return left;
  }

  private parseUnary(field: string): ParsedExpression {
    if (this.peek.type === 'OPERATOR' && this.peek.value === '!') {
      this.advance();
      const expr = this.parsePrimary(field);
      return {
        sql: expr.sql.startsWith('(') && expr.sql.endsWith(')') ? `NOT ${expr.sql}` : `NOT (${expr.sql})`,
        params: expr.params
      };
    }
    return this.parsePrimary(field);
  }

  private parsePrimary(field: string): ParsedExpression {
    const token = this.peek;

    if (token.type === 'METHOD') {
      const method = this.advance().value as StringMethod;
      // No LPAREN expected; tokenizer consumed '('
      const argToken = this.expectNumberOrString();
      this.expect('RPAREN');

      // Validate: method argument must be STRING, not NUMBER
      if (argToken.type !== 'STRING') {
        throw new Error(`Method ${method} requires a string argument at position ${argToken.position}`);
      }

      const arg: string = argToken.value;
      return parseStringMethod(field, method, arg);
    }

    if (token.type === 'NUMBER') {
      const start = parseFloat(token.value);
      this.advance();

      if (this.peek.type === 'RANGE') {
        this.advance();
        const nextToken = this.peek;
        if (nextToken.type !== 'NUMBER') {
          throw new Error(`Expected number after range operator at position ${nextToken.position}`);
        }
        const endToken = this.expectNumber();
        const end = parseFloat(endToken.value);

        return {
          sql: `(${field} >= ? AND ${field} <= ?)`,
          params: [start, end]
        };
      } else {
        throw new Error(`Expected range operator '..' after number at position ${token.position}`);
      }
    }

    if (token.type === 'OPERATOR') {
      const op = this.advance().value;
      const valueToken = this.expectNumberOrString();
      let value: any = valueToken.value;

      if (valueToken.type === 'NUMBER') {
        value = parseFloat(value);
      }

      return {
        sql: `${field} ${op} ?`,
        params: [value]
      };
    }

    if (token.type === 'LPAREN') {
      this.advance();
      const expr = this.parseOr(field);
      this.expect('RPAREN');
      return {
        sql: `(${expr.sql})`,
        params: expr.params
      };
    }

    throw new Error(`Unexpected token at position ${token.position}: ${token.value}`);
  }

  private expectNumber(): Token {
    const token = this.advance();
    if (token.type !== 'NUMBER') {
      throw new Error(`Expected number at position ${token.position}`);
    }
    return token;
  }

  private expectNumberOrString(): Token {
    const token = this.advance();
    if (token.type !== 'NUMBER' && token.type !== 'STRING') {
      throw new Error(`Expected number or string at position ${token.position}`);
    }
    return token;
  }

  private expect(type: Token['type']): Token {
    const token = this.advance();
    if (token.type !== type) {
      throw new Error(`Expected ${type} at position ${token.position}, got ${token.type}`);
    }
    return token;
  }
}

function parseStringMethod(field: string, method: StringMethod, arg: string): ParsedExpression {
  let pattern: string;

  switch (method) {
    case 'starts_with':
      pattern = arg + '%';
      break;
    case 'ends_with':
      pattern = '%' + arg;
      break;
    case 'has':
      pattern = '%' + arg + '%';
      break;
    default:
      throw new Error(`Unknown string method: ${method}`);
  }

  return {
    sql: `${field} LIKE ?`,
    params: [pattern]
  };
}

export function buildWhereClause(filters: Filters): { where: string; params: any[] } {
  const conditions: string[] = [];
  const params: any[] = [];

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
          const pattern = instanceType.replace(/\*/g, '%');
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

export function parseExpression(field: string, expr: string): ParsedExpression {
  try {
    const tokens = tokenize(expr);
    const parser = new ExpressionParser(tokens);
    return parser.parse(field);
    } catch (error) {
      if (env.DEV) {
        console.error(`Error parsing expression for field "${field}":`, error);
      }
      throw error;
    }
}

export type { Token, FilterOperator, LogicalOp, StringMethod, FilterExpression, Filters };
export { tokenize };
