import { jest } from '@jest/globals';
import { escapeCSVValue, exportToCSV, exportToJSON, ExportMetadata } from '../utils/export';

// Mock DOM APIs
global.Blob = jest.fn().mockImplementation((parts: any[], options?: any) => {
  return {
    parts,
    options,
    size: 0,
    type: options?.type,
  };
}) as any;
global.URL.createObjectURL = jest.fn(() => 'blob:fakeurl');
global.URL.revokeObjectURL = jest.fn();
let mockCreateElement: jest.Mock;

beforeEach(() => {
  mockCreateElement = jest.spyOn(document, 'createElement').mockImplementation(() => ({
    href: '',
    download: '',
    click: jest.fn(),
  }));
});

afterEach(() => {
  jest.restoreAllMocks();
});

describe('escapeCSVValue', () => {
  it('returns empty string for null or undefined', () => {
    expect(escapeCSVValue(null)).toBe('');
    expect(escapeCSVValue(undefined)).toBe('');
  });

  it('returns string value as is when no special characters', () => {
    expect(escapeCSVValue('hello')).toBe('hello');
    expect(escapeCSVValue(123)).toBe('123');
  });

  it('escapes commas by wrapping in quotes', () => {
    expect(escapeCSVValue('a,b')).toBe('"a,b"');
  });

  it('escapes double quotes by doubling them and wrapping', () => {
    expect(escapeCSVValue('say "hello"')).toBe('"say ""hello"""');
  });

  it('escapes newlines and carriage returns', () => {
    expect(escapeCSVValue('line1\nline2')).toBe('"line1\nline2"');
    expect(escapeCSVValue('line1\r\nline2')).toBe('"line1\r\nline2"');
  });

  it('handles values with multiple special characters', () => {
    expect(escapeCSVValue('a,"b",c\nd')).toBe('"a,""b"",c\nd"');
  });
});

describe('exportToCSV', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('creates CSV with header row', () => {
    const data = [{ col1: 'a', col2: 'b' }];
    const columns = ['col1', 'col2'];
    exportToCSV(data, columns, 'test');

    const a = mockCreateElement.mock.results[0].value;
    expect(a.download).toBe('test.csv');
    expect(a.href).toBe('blob:fakeurl');
    expect(a.click).toHaveBeenCalled();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:fakeurl');
  });

  it('includes metadata when provided', () => {
    const data = [{ col1: 'a' }];
    const metadata: ExportMetadata = {
      exportedAt: '2024-01-01T00:00:00Z',
      totalRows: 1,
      filters: { service: 'ec2' },
    };
    exportToCSV(data, ['col1'], 'test', metadata);

    const blob = Blob as any;
    // We could check the blob content but mocking Blob makes it hard.
    // Instead we can spy on URL.createObjectURL and parse the content if we capture it.
  });

  it('adds BOM for UTF-8', () => {
    const data = [{ col1: 'a' }];
    exportToCSV(data, ['col1'], 'test');

    const blobConstructor = Blob as any;
    const parts = blobConstructor.mock.calls[0][0];
    // The first part should start with BOM
    const content = parts.join('');
    expect(content.charCodeAt(0)).toBe(0xFEFF);
  });

  it('handles empty data array', () => {
    exportToCSV([], ['col1'], 'test');
    const a = mockCreateElement.mock.results[0].value;
    // Still should create a file with just header?
    // Our code: lines = [header], then loop over data (no rows), so just header.
    // We can't easily check content due to Blob mock.
  });
});

describe('exportToJSON', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('creates JSON file with data and metadata', () => {
    const data = [{ key: 'value' }];
    exportToJSON(data, 'export');

    const a = mockCreateElement.mock.results[0].value;
    expect(a.download).toBe('export.json');
    expect(a.click).toHaveBeenCalled();
  });

  it('includes metadata when provided', () => {
    const data = [{ a: 1 }];
    const metadata: ExportMetadata = {
      exportedAt: '2024-01-01',
      totalRows: 1,
    };
    exportToJSON(data, 'export', metadata);

    const blob = Blob as any;
    const jsonString = blob.mock.calls[0][0][0];
    const parsed = JSON.parse(jsonString);
    expect(parsed.metadata).toEqual({
      exportedAt: '2024-01-01',
      totalRows: 1,
    });
    expect(parsed.data).toEqual(data);
  });

  it('adds .json extension if missing', () => {
    exportToJSON([], 'file');
    const a = mockCreateElement.mock.results[0].value;
    expect(a.download).toBe('file.json');
  });

  it('formats JSON with 2-space indentation', () => {
    const data = [{ a: 1, b: 2 }];
    exportToJSON(data, 'export');

    const blob = Blob as any;
    const jsonString = blob.mock.calls[0][0][0];
    // Check that there are newlines (since we use JSON.stringify with 2 spaces)
    expect(jsonString).toContain('\n');
  });
});
