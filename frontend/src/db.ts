import type { createSQLiteThread } from 'sqlite-wasm-http';
import type { ResultArray } from 'sqlite-wasm-http/sqlite3-worker1-promiser.js';
import env from './env';


function safeAlert(message: string): void {
  try {
    if (typeof alert === 'function') {
      alert(message);
    } else {
      console.error(message);
    }
  } catch {
    console.error(message);
  }
}

export const DB_URL = env.VITE_USE_TEST_DB
  ? './data/test_aws_pricing.sqlite3'
  : './data/aws_pricing.sqlite3';

export const HTTP_BACKEND_CONFIG = {
  maxPageSize: 4096,
  timeout: 10000,
  cacheSize: 8192,
    sync: true, // 8 MB cache
};

export interface QueryResult {
  columns: string[];
  values: any[][];
}

export class Database {
  private db!: Awaited<ReturnType<typeof createSQLiteThread>>;
  private httpBackend: any;
  private isOpen: boolean = false;

  async init(): Promise<void> {
    try {
      const { createSQLiteThread, createHttpBackend } = await import('sqlite-wasm-http');

      this.httpBackend = createHttpBackend(HTTP_BACKEND_CONFIG);
      this.db = await createSQLiteThread({ http: this.httpBackend });

      // Open database with timeout
      await this.withTimeout(
        this.db('open', {
          filename: 'file:' + encodeURI(DB_URL),
          vfs: 'http'
        }),
        HTTP_BACKEND_CONFIG.timeout
      );

      this.isOpen = true;
      if (env.DEV) {
        console.log('Database opened');
      }
     } catch (error: any) {
       // Log detailed error to console regardless of environment
       console.error('Database initialization failed:', error);
       console.error('Error details:', {
         message: error.message,
         stack: error.stack,
         name: error.name
       });

       if (error.message?.includes('SharedArrayBuffer')) {
         safeAlert('Your browser does not support SharedArrayBuffer required for SQLite WASM. Please use a modern browser with cross-origin isolation enabled.');
       } else if (error.message?.includes('fetch') || error.message?.includes('network')) {
         safeAlert('Failed to load database. Please check your internet connection and refresh the page.');
       } else {
         alert(`Failed to initialize database: ${error.message || 'Unknown error'}. Please check console for details.`);
       }
       throw error;
     }
  }

  async query(sql: string, params: any[] = []): Promise<Record<string, any>[]> {
    if (!this.isOpen) {
      throw new Error('Database not initialized. Call init() first.');
    }

    try {
      const columns: string[] = [];
      const values: any[][] = [];

      await this.withTimeout(
        this.db('exec', {
          sql,
          bind: params,
          rowMode: 'array',
          callback: (msg: ResultArray) => {
            if (msg.row) {
              if (columns.length === 0) {
                columns.push(...msg.columnNames);
              }
              values.push(msg.row);
            }
          },
        }),
        HTTP_BACKEND_CONFIG.timeout
      );

      if (values.length === 0) {
        return [];
      }

      return values.map(vals => {
        const obj: Record<string, any> = {};
        columns.forEach((col: string, i: number) => {
          obj[col] = vals[i];
        });
        return obj;
      });
      } catch (error: any) {
        if (env.DEV) {
          console.error('Query failed:', sql, error);
        }
        throw new Error(`Query failed: ${error.message}`);
      }
  }

   async close(): Promise<void> {
    try {
      if (this.db) {
        await this.db('close', {});
        if (typeof this.db.close === 'function') {
          this.db.close();
        }
        this.isOpen = false;
      }
     } catch (error) {
        if (env.DEV) {
          console.error('Error closing database:', error);
        }
     }

     try {
       if (this.httpBackend) {
         await this.httpBackend.close();
       }
      } catch (error) {
        if (env.DEV) {
          console.error('Error closing HTTP backend:', error);
        }
      }
  }

  async getBytesRead(): Promise<number> {
    return this.db ? (this.db as any).worker.bytesRead : 0;
  }

  private async withTimeout<T>(promise: Promise<T>, ms: number): Promise<T> {
    const timeout = new Promise<never>((_, reject) => {
      setTimeout(() => reject(new Error(`Operation timed out after ${ms}ms`)), ms);
    });
    const result = await Promise.race([promise, timeout]);
    return result as T;
  }
}

export const database = new Database();
export default Database;
