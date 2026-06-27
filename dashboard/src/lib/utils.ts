export function paginate<T>(rows: T[], page: number, perPage: number) {
  const totalRows = rows.length;
  const totalPages = Math.max(1, Math.ceil(totalRows / perPage));
  const safePage = Math.min(Math.max(1, page), totalPages);
  const start = (safePage - 1) * perPage;
  return {
    rows: rows.slice(start, start + perPage),
    page: safePage,
    totalPages,
    totalRows,
  };
}

export function parsePageParam(value: string | string[] | undefined, fallback = 1): number {
  const s = Array.isArray(value) ? value[0] : (value ?? '');
  const n = parseInt(s, 10);
  return isNaN(n) || n < 1 ? fallback : n;
}

export function parsePerPageParam(value: string | string[] | undefined, fallback = 50): number {
  const s = Array.isArray(value) ? value[0] : (value ?? '');
  const n = parseInt(s, 10);
  return isNaN(n) || n < 1 || n > 200 ? fallback : n;
}

export function safeSortColumn(columns: string[], requested: string | string[] | undefined): string {
  const s = Array.isArray(requested) ? requested[0] : (requested ?? null);
  if (s && columns.includes(s)) return s;
  return columns[0] || 'id';
}

export function safeSortOrder(value: string | string[] | undefined): 'ASC' | 'DESC' {
  const s = Array.isArray(value) ? value[0] : (value ?? '');
  return s.toUpperCase() === 'DESC' ? 'DESC' : 'ASC';
}
