'use client';

import Link from 'next/link';

interface Column {
  key: string;
  label: string;
  sortable?: boolean;
}

interface Props {
  columns: Column[];
  rows: Record<string, unknown>[];
  page: number;
  totalPages: number;
  totalRows: number;
  baseUrl: string;
  sort?: string;
  order?: string;
}

export default function DataTable({ columns, rows, page, totalPages, totalRows, baseUrl, sort, order }: Props) {
  const sortUrl = (col: string) => {
    const params = new URLSearchParams();
    params.set('sort', col);
    params.set('order', sort === col && order === 'asc' ? 'desc' : 'asc');
    params.set('page', '1');
    return `${baseUrl}?${params}`;
  };

  const pageUrl = (p: number) => {
    const params = new URLSearchParams();
    if (sort) params.set('sort', sort);
    if (order) params.set('order', order);
    params.set('page', String(p));
    return `${baseUrl}?${params}`;
  };

  return (
    <div>
      <div className="text-sm text-gray-500 mb-2">{totalRows} rows</div>
      <div className="overflow-x-auto border rounded-lg bg-white">
        <table className="w-full text-sm">
          <thead className="bg-gray-100 text-left">
            <tr>
              {columns.map((c) => (
                <th key={c.key} className="px-4 py-2 font-medium">
                  {c.sortable && sort ? (
                    <Link href={sortUrl(c.key)} className="hover:text-blue-600">
                      {c.label} {sort === c.key ? (order === 'asc' ? '↑' : '↓') : ''}
                    </Link>
                  ) : (
                    c.label
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i} className="border-t hover:bg-gray-50">
                {columns.map((c) => (
                  <td key={c.key} className="px-4 py-2 max-w-xs truncate">
                    {String(row[c.key] ?? '')}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {totalPages > 1 && (
        <div className="flex gap-2 mt-4 items-center justify-center text-sm">
          <Link
            href={pageUrl(page - 1)}
            className={`px-3 py-1 rounded border ${page <= 1 ? 'text-gray-300 pointer-events-none' : 'hover:bg-gray-100'}`}
          >
            ← Prev
          </Link>
          <span className="text-gray-500">
            {page} / {totalPages}
          </span>
          <Link
            href={pageUrl(page + 1)}
            className={`px-3 py-1 rounded border ${page >= totalPages ? 'text-gray-300 pointer-events-none' : 'hover:bg-gray-100'}`}
          >
            Next →
          </Link>
        </div>
      )}
    </div>
  );
}
