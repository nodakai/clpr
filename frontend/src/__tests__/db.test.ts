import { jest, describe, it, expect, beforeEach } from '@jest/globals';

// Mock the sqlite-wasm-http module
const mockCreateSQLiteThread = jest.fn();
const mockCreateHttpBackend = jest.fn();

let mockDb: any;
let mockHttpBackendInstance: any;

beforeEach(() => {
  jest.clearAllMocks();

  mockHttpBackendInstance = {
    close: jest.fn(),
  };

  mockDb = jest.fn();
  mockDb.close = jest.fn();
  mockDb.worker = { bytesRead: 12345 };

  mockDb.mockImplementation(async (command: string, config: any) => {
    switch (command) {
      case 'open':
        return undefined;
      case 'close':
        return undefined;
      case 'exec':
        return new Promise<void>((resolve) => {
          if (config.callback && !config.error) {
            config.callback({
              row: ['value1', 'value2'],
              columnNames: ['col1', 'col2'],
            });
          }
          resolve(undefined);
        });
      default:
        return undefined;
    }
  });

  mockCreateHttpBackend.mockReturnValue(mockHttpBackendInstance);
  mockCreateSQLiteThread.mockReturnValue(Promise.resolve(mockDb));
});

jest.unstable_mockModule('sqlite-wasm-http', () => ({ createSQLiteThread: mockCreateSQLiteThread, createHttpBackend: mockCreateHttpBackend }));

const { Database } = await import('../db');

describe('Database', () => {
  let database: Database;

  beforeEach(() => {
    database = new Database();
  });

  describe('init()', () => {
    it('initializes database successfully', async () => {
      await database.init();

      expect(mockCreateHttpBackend).toHaveBeenCalledWith({
        maxPageSize: 4096,
        timeout: 10000,
        cacheSize: 8192,
        sync: true,
      });
      expect(mockCreateSQLiteThread).toHaveBeenCalledWith({
        http: mockHttpBackendInstance,
      });
      expect(mockDb).toHaveBeenCalledWith('open', expect.any(Object));
      expect(database['isOpen']).toBe(true);
    });

    it('logs "Database opened" in DEV mode', async () => {
      const consoleSpy = jest.spyOn(console, 'log').mockImplementation(() => {});
      await database.init();
      expect(consoleSpy).toHaveBeenCalledWith('Database opened');
      consoleSpy.mockRestore();
    });

    it('throws error with SharedArrayBuffer message', async () => {
      const error = new Error('SharedArrayBuffer is not supported');
      mockCreateSQLiteThread.mockRejectedValueOnce(error);
      await expect(database.init()).rejects.toThrow('SharedArrayBuffer is not supported');
    });

    it('throws error with network failure message', async () => {
      const error = new Error('Failed to fetch database');
      mockCreateSQLiteThread.mockRejectedValueOnce(error);
      await expect(database.init()).rejects.toThrow('Failed to fetch database');
    });

    it('throws generic error on initialization failure', async () => {
      const error = new Error('Unknown error');
      mockCreateSQLiteThread.mockRejectedValueOnce(error);
      await expect(database.init()).rejects.toThrow('Unknown error');
    });
  });

  describe('query()', () => {
    beforeEach(async () => {
      await database.init();
    });

    it('executes query and returns results as objects', async () => {
      const result = await database.query('SELECT * FROM prices', []);

      expect(result).toHaveLength(1);
      expect(result[0]).toEqual({ col1: 'value1', col2: 'value2' });
      expect(mockDb).toHaveBeenCalledWith(
        'exec',
        expect.objectContaining({
          sql: 'SELECT * FROM prices',
          bind: [],
          rowMode: 'array',
          callback: expect.any(Function),
        })
      );
    });

    it('handles empty result set', async () => {
      mockDb.mockImplementation(async (command: string, config: any) => {
        if (command === 'exec') {
          return new Promise<void>((resolve) => {
            if (config.callback) {
              config.callback({ row: null });
            }
            resolve(undefined);
          });
        }
        return undefined;
      });

      const result = await database.query('SELECT * FROM prices WHERE 1=0', []);

      expect(result).toEqual([]);
    });

    it('throws error when database not initialized', async () => {
      const freshDb = new Database();
      await expect(freshDb.query('SELECT 1')).rejects.toThrow('Database not initialized. Call init() first.');
    });

    it('throws error on query failure', async () => {
      mockDb.mockRejectedValueOnce(new Error('SQL syntax error'));

      await expect(database.query('SELECT * FROM')).rejects.toThrow('Query failed: SQL syntax error');
    });

    it('handles multiple rows in result', async () => {
      mockDb.mockImplementation(async (command: string, config: any) => {
        if (command === 'exec') {
          return new Promise<void>((resolve) => {
            if (config.callback) {
              config.callback({ row: ['row1col1', 'row1col2'], columnNames: ['col1', 'col2'] });
              config.callback({ row: ['row2col1', 'row2col2'], columnNames: ['col1', 'col2'] });
            }
            resolve(undefined);
          });
        }
        return undefined;
      });

      const result = await database.query('SELECT * FROM prices', []);

      expect(result).toHaveLength(2);
      expect(result[0]).toEqual({ col1: 'row1col1', col2: 'row1col2' });
      expect(result[1]).toEqual({ col1: 'row2col1', col2: 'row2col2' });
    });

    it('handles query parameters correctly', async () => {
      await database.query('SELECT * FROM prices WHERE service = ? AND os = ?', ['ec2', 'Linux']);

      expect(mockDb).toHaveBeenCalledWith(
        'exec',
        expect.objectContaining({
          sql: 'SELECT * FROM prices WHERE service = ? AND os = ?',
          bind: ['ec2', 'Linux'],
          rowMode: 'array',
          callback: expect.any(Function),
        })
      );
    });
  });

  describe('close()', () => {
    it('closes database and HTTP backend', async () => {
      await database.init();
      await database.close();

      expect(mockDb.close).toHaveBeenCalled();
      expect(mockHttpBackendInstance.close).toHaveBeenCalled();
      expect(database['isOpen']).toBe(false);
    });

    it('handles close errors gracefully', async () => {
      await database.init();
      mockDb.mockRejectedValueOnce(new Error('Close failed'));
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

      await database.close();

      expect(consoleSpy).toHaveBeenCalledWith('Error closing database:', expect.any(Error));
      consoleSpy.mockRestore();
    });

    it('does nothing if database not initialized', async () => {
      const freshDb = new Database();
      await freshDb.close(); // Should not throw
    });
  });

  describe('getBytesRead()', () => {
    it('returns bytes read from worker', async () => {
      await database.init();
      const bytes = await database.getBytesRead();
      expect(bytes).toBe(12345);
    });

    it('returns 0 if db not initialized', async () => {
      const freshDb = new Database();
      const bytes = await freshDb.getBytesRead();
      expect(bytes).toBe(0);
    });
  });

  describe('withTimeout()', () => {
    it('resolves with result when operation completes within timeout', async () => {
      await database.init();
      const result = await database['withTimeout'](Promise.resolve('success'), 1000);
      expect(result).toBe('success');
    });

    it('rejects with timeout error when operation exceeds timeout', async () => {
      await database.init();
      const slowPromise = new Promise<string>((resolve) => {
        setTimeout(() => resolve('slow'), 5000);
      });

      await expect(database['withTimeout'](slowPromise, 100)).rejects.toThrow(
        'Operation timed out after 100ms'
      );
    });
  });
});
