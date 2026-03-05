/**
 * Unit tests for query-builder.ts module.
 * Tests parseExpression and buildWhereClause functions.
 */

import { jest, describe, it, expect, beforeEach, afterEach } from '@jest/globals';

import { parseExpression, buildWhereClause, tokenize, type Token } from '../query-builder';

beforeEach(() => {
  jest.spyOn(console, 'error').mockImplementation(() => {});
});

afterEach(() => {
  (console.error as jest.Mock).mockRestore();
});

describe('parseExpression', () => {
  describe('range expressions with ".."', () => {
    it('parses ">=4 && <=8" as separate conditions', () => {
      // Note: This is not a single range operator but two comparison operators
      // The syntax ">=4 && <=8" should be parsed as two separate comparisons
      const result1 = parseExpression('field', '>=4');
      expect(result1.sql).toBe('field >= ?');
      expect(result1.params).toEqual([4]);

      const result2 = parseExpression('field', '<=8');
      expect(result2.sql).toBe('field <= ?');
      expect(result2.params).toEqual([8]);
    });

    it('parses "2..4" as range', () => {
      const result = parseExpression('field', '2..4');
      expect(result.sql).toBe('(field >= ? AND field <= ?)');
      expect(result.params).toEqual([2, 4]);
    });

    it('parses "!5..10" as negated range', () => {
      const result = parseExpression('field', '!5..10');
      expect(result.sql).toBe('NOT (field >= ? AND field <= ?)');
      expect(result.params).toEqual([5, 10]);
    });

    it('parses decimal ranges', () => {
      const result = parseExpression('field', '1.5..3.5');
      expect(result.sql).toBe('(field >= ? AND field <= ?)');
      expect(result.params).toEqual([1.5, 3.5]);
    });

    it('requires number before range operator', () => {
      expect(() => parseExpression('field', '..4')).toThrow();
    });

    it('requires number after range operator', () => {
      expect(() => parseExpression('field', '2..')).toThrow();
    });
  });

  describe('comparison operators', () => {
    it('parses ">=" operator', () => {
      const result = parseExpression('field', '>=10');
      expect(result.sql).toBe('field >= ?');
      expect(result.params).toEqual([10]);
    });

    it('parses "<=" operator', () => {
      const result = parseExpression('field', '<=100');
      expect(result.sql).toBe('field <= ?');
      expect(result.params).toEqual([100]);
    });

    it('parses ">" operator', () => {
      const result = parseExpression('field', '>5');
      expect(result.sql).toBe('field > ?');
      expect(result.params).toEqual([5]);
    });

    it('parses "<" operator', () => {
      const result = parseExpression('field', '<20');
      expect(result.sql).toBe('field < ?');
      expect(result.params).toEqual([20]);
    });

    it('parses "=" operator', () => {
      const result = parseExpression('field', '=5');
      expect(result.sql).toBe('field = ?');
      expect(result.params).toEqual([5]);
    });

    it('parses "!=" operator', () => {
      const result = parseExpression('field', '!=5');
      expect(result.sql).toBe('field != ?');
      expect(result.params).toEqual([5]);
    });
  });

  describe('string method calls', () => {
    it('parses starts_with("prefix")', () => {
      const result = parseExpression('field', 'starts_with("m5.")');
      expect(result.sql).toBe('field LIKE ?');
      expect(result.params).toEqual(['m5.%']);
    });

    it('parses starts_with with single quotes', () => {
      const result = parseExpression('field', "starts_with('t3.')");
      expect(result.sql).toBe('field LIKE ?');
      expect(result.params).toEqual(['t3.%']);
    });

    it('parses ends_with("suffix")', () => {
      const result = parseExpression('field', 'ends_with(".large")');
      expect(result.sql).toBe('field LIKE ?');
      expect(result.params).toEqual(['%.large']);
    });

    it('parses has("substring")', () => {
      const result = parseExpression('field', 'has("nano")');
      expect(result.sql).toBe('field LIKE ?');
      expect(result.params).toEqual(['%nano%']);
    });

    it('handles escaped quotes in string', () => {
      const result = parseExpression('field', 'starts_with("a\\"b")');
      expect(result.sql).toBe('field LIKE ?');
      expect(result.params).toEqual(['a"b%']);
    });
  });

  describe('parentheses and grouping', () => {
    it('parses parenthesized expressions', () => {
      const result = parseExpression('field', '(>=2)');
      expect(result.sql).toBe('(field >= ?)');
      expect(result.params).toEqual([2]);
    });

    it('handles nested parentheses', () => {
      const result = parseExpression('field', '((>=2 && <=4))');
      expect(result.sql).toBe('(((field >= ? AND field <= ?)))');
      expect(result.params).toEqual([2, 4]);
    });
  });

  describe('logical operators', () => {
    it('parses ">=4 && <=8" as combined AND expression', () => {
      const result = parseExpression('field', '>=4 && <=8');
      expect(result.sql).toBe('(field >= ? AND field <= ?)');
      expect(result.params).toEqual([4, 8]);
    });

    it('parses "||" as OR', () => {
      const result = parseExpression('field', '=2 || =4');
      expect(result.sql).toBe('(field = ? OR field = ?)');
      expect(result.params).toEqual([2, 4]);
    });

    it('handles complex mixed expressions', () => {
      const result = parseExpression('field', '(>=2 && <=4) || >=10');
      expect(result.sql).toBe('(((field >= ? AND field <= ?)) OR field >= ?)');
      expect(result.params).toEqual([2, 4, 10]);
    });

    it('handles multiple AND conditions', () => {
      const result = parseExpression('field', '>=1 && <=10 && !=5');
      expect(result.sql).toBe('((field >= ? AND field <= ?) AND field != ?)');
      expect(result.params).toEqual([1, 10, 5]);
    });

    it('handles negation with logical AND', () => {
      const result = parseExpression('field', '! (=5 && =10)');
      expect(result.sql).toBe('NOT ((field = ? AND field = ?))');
      expect(result.params).toEqual([5, 10]);
    });
  });

  describe('edge cases', () => {
    it('throws on unexpected token', () => {
      expect(() => parseExpression('field', '@invalid')).toThrow();
    });

    it('throws on incomplete range', () => {
      expect(() => parseExpression('field', '2..')).toThrow();
    });

    it('handles negative numbers', () => {
      const result = parseExpression('field', '>=-10 && <=10');
      expect(result.params).toEqual([-10, 10]);
    });
  });

  describe('whitespace handling', () => {
    it('parses expression with leading/trailing whitespace', () => {
      const result = parseExpression('field', ' >= 4 ');
      expect(result.sql).toBe('field >= ?');
      expect(result.params).toEqual([4]);
    });

    it('parses expression with excess whitespace between tokens', () => {
      const result = parseExpression('field', '  >=4   &&  <=8  ');
      expect(result.sql).toBe('(field >= ? AND field <= ?)');
      expect(result.params).toEqual([4, 8]);
    });

    it('parses expression with whitespace around range operator', () => {
      const result = parseExpression('field', '2 .. 4');
      expect(result.sql).toBe('(field >= ? AND field <= ?)');
      expect(result.params).toEqual([2, 4]);
    });
  });

  describe('invalid syntax errors', () => {
    it('throws on empty string', () => {
      expect(() => parseExpression('field', '')).toThrow();
    });

    it('throws on lone logical operator', () => {
      expect(() => parseExpression('field', '&&')).toThrow();
      expect(() => parseExpression('field', '||')).toThrow();
    });

    it('throws on incomplete range operator at start', () => {
      expect(() => parseExpression('field', '..4')).toThrow();
    });

    it('throws on method name without parentheses', () => {
      expect(() => parseExpression('field', 'starts_with')).toThrow();
    });

    it('throws on string method with non-string argument', () => {
      expect(() => parseExpression('field', 'starts_with(123)')).toThrow();
      expect(() => parseExpression('field', 'ends_with(456)')).toThrow();
      expect(() => parseExpression('field', 'has(789)')).toThrow();
    });

    it('throws on unknown method name', () => {
      expect(() => parseExpression('field', 'unknown_method("arg")')).toThrow();
    });

    it('throws on expression starting with range operator', () => {
      expect(() => parseExpression('field', '>=5..')).toThrow();
    });
  });

  describe('string escaping and quotes', () => {
    it('handles single quote inside double-quoted string', () => {
      const result = parseExpression('field', 'starts_with("m\'5.")');
      expect(result.sql).toBe('field LIKE ?');
      expect(result.params).toEqual(["m'5.%"]);
    });

    it('handles double quote inside single-quoted string', () => {
      const result = parseExpression('field', "has('\"quoted\"')");
       expect(result.sql).toBe('field LIKE ?');
      expect(result.params).toEqual(['%"quoted"%']);
    });

    it('handles empty string in string method', () => {
      const result = parseExpression('field', 'starts_with("")');
      expect(result.sql).toBe('field LIKE ?');
      expect(result.params).toEqual(['%']);
    });

    it('handles empty string in has method', () => {
      const result = parseExpression('field', 'has("")');
      expect(result.sql).toBe('field LIKE ?');
      expect(result.params).toEqual(['%%']);
    });

    it('handles O\'Reilly with internal quote', () => {
      const result = parseExpression('field', 'starts_with("O\'Reilly")');
      expect(result.sql).toBe('field LIKE ?');
      expect(result.params).toEqual(["O'Reilly%"]);
    });
  });

  describe('logical operator precedence', () => {
    it('parses && with higher precedence than ||', () => {
      const result = parseExpression('field', '>=2 && <=4 || >=10');
      expect(result.sql).toBe('((field >= ? AND field <= ?) OR field >= ?)');
      expect(result.params).toEqual([2, 4, 10]);
    });

    it('parses || with lower precedence than &&', () => {
      const result = parseExpression('field', '=2 || =4 && =6');
      expect(result.sql).toBe('(field = ? OR (field = ? AND field = ?))');
      expect(result.params).toEqual([2, 4, 6]);
    });

    it('handles multiple || and && combinations', () => {
      const result = parseExpression('field', '>=1 && <=5 || >=10 && <=15 || =20');
      expect(result.sql).toBe('(((field >= ? AND field <= ?) OR (field >= ? AND field <= ?)) OR field = ?)');
      expect(result.params).toEqual([1, 5, 10, 15, 20]);
    });
  });

  describe('multiple parentheses and nesting', () => {
    it('parses parentheses around range expression', () => {
      const result = parseExpression('field', '(>=2 && <=4)');
      expect(result.sql).toBe('((field >= ? AND field <= ?))');
      expect(result.params).toEqual([2, 4]);
    });

    it('parses complex nested parentheses', () => {
      const result = parseExpression('field', '(>=2 && <=4) || (>=10)');
      expect(result.sql).toBe('(((field >= ? AND field <= ?)) OR (field >= ?))');
      expect(result.params).toEqual([2, 4, 10]);
    });

    it('handles deeply nested parentheses', () => {
      const result = parseExpression('field', '(((>=2 && <=4) || >=10) && !=5)');
      expect(result.sql).toBe('((((((field >= ? AND field <= ?)) OR field >= ?)) AND field != ?))');
      expect(result.params).toEqual([2, 4, 10, 5]);
    });

    it('handles redundant double parentheses', () => {
      const result = parseExpression('field', '((>=2))');
      expect(result.sql).toBe('((field >= ?))');
      expect(result.params).toEqual([2]);
    });
  });

  describe('numeric precision and large numbers', () => {
    it('parses small decimal numbers', () => {
      const result = parseExpression('field', '>=0.001');
      expect(result.params).toEqual([0.001]);
    });

    it('parses large integers', () => {
      const result = parseExpression('field', '<=999999999');
      expect(result.params).toEqual([999999999]);
    });

    it('parses decimal range with precision', () => {
      const result = parseExpression('field', '0.12345..0.67890');
      expect(result.params).toEqual([0.12345, 0.6789]);
    });
  });

  describe('negative numbers', () => {
    it('parses negative numbers after operator', () => {
      const result = parseExpression('field', '<= -10');
      expect(result.params).toEqual([-10]);
    });

    it('parses negative range', () => {
      const result = parseExpression('field', '-20..-5');
      expect(result.sql).toBe('(field >= ? AND field <= ?)');
      expect(result.params).toEqual([-20, -5]);
    });

    it('parses negative numbers with &&', () => {
      const result = parseExpression('field', '>=-100 && <=-50');
      expect(result.params).toEqual([-100, -50]);
    });
  });

  describe('empty filters', () => {
    it('returns default where clause for empty filter object', () => {
      const result = buildWhereClause({});
      expect(result.where).toBe('1=1');
      expect(result.params).toEqual([]);
    });
  });

  describe('unknown fields', () => {
    it('includes unknown fields in WHERE clause', () => {
      const result = buildWhereClause({ unknown_field: '>=4' } as any);
      expect(result.where).toContain('unknown_field >= ?');
      expect(result.params).toContain(4);
    });
  });

  describe('string method argument variations', () => {
    it('handles empty string pattern in starts_with', () => {
      const result = buildWhereClause({ instance_type: 'starts_with("")' });
      expect(result.where).toBe('instance_type LIKE ?');
      expect(result.params).toEqual(['%']);
    });

    it('handles empty string pattern in has', () => {
      const result = buildWhereClause({ instance_type: 'has("")' });
      expect(result.where).toBe('instance_type LIKE ?');
      expect(result.params).toEqual(['%%']);
    });

    it('handles quote inside pattern', () => {
      const result = buildWhereClause({ instance_type: 'starts_with("O\'Reilly")' });
      expect(result.params).toEqual(["O'Reilly%"]);
    });

    it('handles special characters in pattern', () => {
      const result = buildWhereClause({ instance_type: 'has("100%")' });
      expect(result.params).toEqual(['%100%%']);
    });

    it('handles underscore in pattern', () => {
      const result = buildWhereClause({ instance_type: 'ends_with("_large")' });
      expect(result.params).toEqual(['%_large']);
    });
  });

  describe('complex combined filters', () => {
    it('handles expression with precedence and parentheses', () => {
      const result = buildWhereClause({
        vcpu: '>=2 && <=4 || >=10',
        memory_gb: '>=8'
      });
      expect(result.where).toContain('(');
      expect(result.where).toContain('AND');
      expect(result.where).toContain('OR');
      expect(result.params).toContain(2);
      expect(result.params).toContain(4);
      expect(result.params).toContain(10);
      expect(result.params).toContain(8);
    });

    it('handles multiple expression fields with complex logic', () => {
      const result = buildWhereClause({
        vcpu: '>=2 && <=4',
        memory_gb: '>=8 && <=32',
        service: 'ec2'
      });
      expect(result.where).toBe('(vcpu >= ? AND vcpu <= ?) AND (memory_gb >= ? AND memory_gb <= ?) AND service = ?');
      expect(result.params).toEqual([2, 4, 8, 32, 'ec2']);
    });
  });

  describe('tokenizer edge cases', () => {
    it('tokenizes negative sign as part of number', () => {
      const tokens = tokenize('<= -10');
      const numberToken = tokens.find((t: Token) => t.type === 'NUMBER');
      expect(numberToken?.value).toBe('-10');
    });

    it('tokenizes method names correctly', () => {
      const tokens = tokenize('starts_with("m5.")');
      expect(tokens[0].type).toBe('METHOD');
      expect(tokens[0].value).toBe('starts_with');
    });

    it('tokenizes string method with quote inside', () => {
      const tokens = tokenize('has("it\'s")');
      const stringToken = tokens.find((t: Token) => t.type === 'STRING');
      expect(stringToken?.value).toBe("it's");
    });
  });
});

describe('buildWhereClause', () => {
  describe('simple field filters', () => {
    it('builds simple equality condition for service', () => {
      const result = buildWhereClause({ service: 'ec2' });
      expect(result.where).toBe('service = ?');
      expect(result.params).toEqual(['ec2']);
    });

    it('builds simple equality condition for instance_type', () => {
      const result = buildWhereClause({ instance_type: 'm5.large' });
      expect(result.where).toBe('instance_type = ?');
      expect(result.params).toEqual(['m5.large']);
    });

    it('builds simple equality condition for family', () => {
      const result = buildWhereClause({ family: ' general' });
      expect(result.where).toBe('family = ?');
      expect(result.params).toEqual([' general']);
    });

    it('combines multiple simple filters with AND', () => {
      const result = buildWhereClause({
        service: 'ec2',
        instance_type: 'm5.large',
      });
      expect(result.where).toBe('service = ? AND instance_type = ?');
      expect(result.params).toEqual(['ec2', 'm5.large']);
    });
  });

  describe('array filters', () => {
    it('builds IN clause for single region', () => {
      const result = buildWhereClause({ region: 'us-east-1' });
      expect(result.where).toContain('region IN (?)');
      expect(result.params).toContain('us-east-1');
    });

    it('builds IN clause for multiple regions', () => {
      const result = buildWhereClause({ region: ['us-east-1', 'eu-west-1'] });
      expect(result.where).toBe('region IN (?, ?)');
      expect(result.params).toEqual(['us-east-1', 'eu-west-1']);
    });

    it('builds IN clause for storage_type', () => {
      const result = buildWhereClause({ storage_type: ['ssd', 'hdd'] });
      expect(result.where).toContain('storage_type IN (?, ?)');
      expect(result.params).toContain('ssd');
      expect(result.params).toContain('hdd');
    });

    it('builds IN clause for os', () => {
      const result = buildWhereClause({ os: ['Linux', 'Windows'] });
      expect(result.where).toContain('os IN (?, ?)');
    });

    it('builds IN clause for tenancy', () => {
      const result = buildWhereClause({ tenancy: ['Shared', 'Dedicated'] });
      expect(result.where).toContain('tenancy IN (?, ?)');
    });

    it('builds IN clause for purchase_option', () => {
      const result = buildWhereClause({ purchase_option: ['OnDemand', 'Reserved'] });
      expect(result.where).toContain('purchase_option IN (?, ?)');
    });

    it('combines array filters with other filters', () => {
      const result = buildWhereClause({
        service: 'ec2',
        region: ['us-east-1', 'eu-west-1'],
      });
      expect(result.where).toBe('service = ? AND region IN (?, ?)');
      expect(result.params).toEqual(['ec2', 'us-east-1', 'eu-west-1']);
    });
  });

  describe('numeric expression filters', () => {
    it('builds condition for vcpu expression', () => {
      const result = buildWhereClause({ vcpu: '>=4' });
      expect(result.where).toBe('vcpu >= ?');
      expect(result.params).toEqual([4]);
    });

    it('builds condition for memory_gb range', () => {
      const result = buildWhereClause({ memory_gb: '4..16' });
      expect(result.where).toBe('(memory_gb >= ? AND memory_gb <= ?)');
      expect(result.params).toEqual([4, 16]);
    });

    it('builds condition for negated range', () => {
      const result = buildWhereClause({ vcpu: '!2..4' });
      expect(result.where).toBe('NOT (vcpu >= ? AND vcpu <= ?)');
      expect(result.params).toEqual([2, 4]);
    });

    it('combines multiple numeric expressions with AND', () => {
      const result = buildWhereClause({
        vcpu: '>=2',
        memory_gb: '>=8',
      });
      expect(result.where).toBe('vcpu >= ? AND memory_gb >= ?');
      expect(result.params).toEqual([2, 8]);
    });
  });

  describe('price range filters', () => {
    it('builds conditions for price_hourly_min', () => {
      const result = buildWhereClause({ price_hourly_min: 0.05 });
      expect(result.where).toContain('hourly >= ?');
      expect(result.params).toContain(0.05);
    });

    it('builds conditions for price_hourly_max', () => {
      const result = buildWhereClause({ price_hourly_max: 1.0 });
      expect(result.where).toContain('hourly <= ?');
      expect(result.params).toContain(1.0);
    });

    it('handles both price_hourly_min and price_hourly_max', () => {
      const result = buildWhereClause({
        price_hourly_min: 0.05,
        price_hourly_max: 0.50,
      });
      expect(result.where).toContain('hourly >= ?');
      expect(result.where).toContain('hourly <= ?');
      expect(result.params).toContain(0.05);
      expect(result.params).toContain(0.50);
    });
  });

  describe('instance_type string methods', () => {
    it('handles starts_with method', () => {
      const result = buildWhereClause({ instance_type: 'starts_with("m5.")' });
      expect(result.where).toBe('instance_type LIKE ?');
      expect(result.params).toEqual(['m5.%']);
    });

    it('handles ends_with method', () => {
      const result = buildWhereClause({ instance_type: 'ends_with(".large")' });
      expect(result.where).toBe('instance_type LIKE ?');
      expect(result.params).toEqual(['%.large']);
    });

    it('handles has method', () => {
      const result = buildWhereClause({ instance_type: 'has("nano")' });
      expect(result.where).toBe('instance_type LIKE ?');
      expect(result.params).toEqual(['%nano%']);
    });

    it('strips quotes from method argument', () => {
      const result = buildWhereClause({ instance_type: 'starts_with("t3.")' });
      expect(result.params).toEqual(['t3.%']);
    });

    it('handles wildcard patterns with *', () => {
      const result = buildWhereClause({ instance_type: 'm5.*' });
      expect(result.where).toBe('instance_type LIKE ?');
      expect(result.params).toEqual(['m5.%']);
    });
  });

  describe('combined filters', () => {
    it('combines all filter types', () => {
      const result = buildWhereClause({
        service: 'ec2',
        region: ['us-east-1', 'eu-west-1'],
        vcpu: '>=2',
        memory_gb: '<=32',
        price_hourly_min: 0.01,
        price_hourly_max: 1.0,
        os: ['Linux'],
      });

      expect(result.where).toContain('service = ?');
      expect(result.where).toContain('region IN (?, ?)');
      expect(result.where).toContain('vcpu >= ?');
      expect(result.where).toContain('memory_gb <= ?');
      expect(result.where).toContain('hourly >= ?');
      expect(result.where).toContain('hourly <= ?');
      expect(result.where).toContain('os IN (?)');

      expect(result.params).toContain('ec2');
      expect(result.params).toContain('us-east-1');
      expect(result.params).toContain('eu-west-1');
      expect(result.params).toContain(2);
      expect(result.params).toContain(32);
      expect(result.params).toContain(0.01);
      expect(result.params).toContain(1.0);
      expect(result.params).toContain('Linux');
    });

    it('returns "1=1" when no filters provided', () => {
      const result = buildWhereClause({});
      expect(result.where).toBe('1=1');
      expect(result.params).toEqual([]);
    });
  });

  describe('error handling', () => {
    it('catches invalid vcpu expression and continues with other filters', () => {
      const consoleSpy = jest.spyOn(console, 'warn').mockImplementation(() => {});
      const result = buildWhereClause({
        service: 'ec2',
        vcpu: 'invalid',
      });

      expect(result.where).toBe('service = ?');
      expect(result.params).toEqual(['ec2']);
      expect(consoleSpy).toHaveBeenCalled();

      consoleSpy.mockRestore();
    });

    it('catches invalid memory_gb expression', () => {
      const consoleSpy = jest.spyOn(console, 'warn').mockImplementation(() => {});
      const result = buildWhereClause({
        memory_gb: 'invalid',
      });

      expect(result.where).toBe('1=1');
      expect(consoleSpy).toHaveBeenCalled();

      consoleSpy.mockRestore();
    });
  });
});
