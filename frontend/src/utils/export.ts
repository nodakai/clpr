export interface ExportMetadata {
  exportedAt: string;
  filters?: Record<string, any>;
  totalRows: number;
}

export function escapeCSVValue(value: any): string {
  if (value === null || value === undefined) {
    return '';
  }
  const stringValue = value.toString();
  // Check if value contains comma, quote, or newline
  if (stringValue.includes(',') || stringValue.includes('"') || stringValue.includes('\n') || stringValue.includes('\r')) {
    // Escape quotes by doubling them and wrap in quotes
    return `"${stringValue.replace(/"/g, '""')}"`;
  }
  return stringValue;
}

export function exportToCSV(
  data: Record<string, any>[],
  columns: string[],
  filename: string,
  metadata?: ExportMetadata
): void {
  const lines: string[] = [];

  // Add metadata as comment rows if provided
  if (metadata) {
    lines.push(`# Exported: ${metadata.exportedAt}`);
    if (metadata.filters) {
      lines.push(`# Filters: ${JSON.stringify(metadata.filters)}`);
    }
    lines.push(`# Total rows in dataset: ${metadata.totalRows}`);
    lines.push(''); // Empty line before data
  }

  // Add header row
  lines.push(columns.map(col => `"${col}"`).join(','));

  // Add data rows
  for (const row of data) {
    const values = columns.map(col => escapeCSVValue(row[col]));
    lines.push(values.join(','));
  }

  // Add BOM for UTF-8 and create blob
  const csvContent = '\uFEFF' + lines.join('\n');
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  
  const a = document.createElement('a');
  a.href = url;
  a.download = filename.endsWith('.csv') ? filename : `${filename}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

export function exportToJSON(
  data: Record<string, any>[],
  filename: string,
  metadata?: ExportMetadata
): void {
  const exportObj: Record<string, any> = {};
  
  if (metadata) {
    exportObj.metadata = {
      exportedAt: metadata.exportedAt,
      totalRows: metadata.totalRows,
    };
    if (metadata.filters) {
      exportObj.metadata.filters = metadata.filters;
    }
  }
  
  exportObj.data = data;

  const jsonContent = JSON.stringify(exportObj, null, 2);
  const blob = new Blob([jsonContent], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  
  const a = document.createElement('a');
  a.href = url;
  a.download = filename.endsWith('.json') ? filename : `${filename}.json`;
  a.click();
  URL.revokeObjectURL(url);
}
