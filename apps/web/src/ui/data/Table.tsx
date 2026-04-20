// [v84-1-5][front-nextjs:ui]
'use client';

import type { ReactNode } from 'react';

export interface TableColumn<T> {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  className?: string;
}

export interface TableProps<T> {
  columns: TableColumn<T>[];
  data: T[];
  keyExtractor: (row: T) => string;
  emptyMessage?: string;
}

export function Table<T>({ columns, data, keyExtractor, emptyMessage = 'No data' }: TableProps<T>) {
  if (data.length === 0) {
    return (
      <div className="rounded-md border border-border p-8 text-center text-sm text-textMuted">
        {emptyMessage}
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-md border border-border">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-border bg-surfaceMuted text-xs font-medium uppercase text-textMuted">
          <tr>
            {columns.map((col) => (
              <th key={col.key} className={`px-4 py-3 ${col.className ?? ''}`}>
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-border text-text">
          {data.map((row) => (
            <tr key={keyExtractor(row)} className="hover:bg-surfaceMuted">
              {columns.map((col) => (
                <td key={col.key} className={`px-4 py-3 ${col.className ?? ''}`}>
                  {col.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
