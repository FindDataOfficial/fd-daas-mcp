// @ts-nocheck
import { getDb, queryAll, getTableColumns } from '@/lib/db';
import { paginate, parsePageParam, parsePerPageParam, safeSortColumn, safeSortOrder } from '@/lib/utils';
import DataTable from '@/components/data-table';
import Link from 'next/link';
import { notFound } from 'next/navigation';

interface Props {
  params: Promise<{ dbName: string; tableName: string }>;
  searchParams: Promise<{ page?: string; perPage?: string; sort?: string; order?: string }>;
}

export default async function TableBrowsePage({ params, searchParams }: Props) {
  const { dbName, tableName } = await params;
  const sp = await searchParams;

  let db;
  try {
    db = await getDb(dbName);
  } catch {
    notFound();
  }

  const colRows = getTableColumns(db, tableName);
  if (!colRows.length) notFound();

  const columnNames = colRows.map((c) => c.name);
  const page = parsePageParam(sp.page);
  const perPage = parsePerPageParam(sp.perPage);
  const sort = safeSortColumn(columnNames, sp.sort);
  const order = safeSortOrder(sp.order);

  const countRow = queryAll(db, `SELECT COUNT(*) as cnt FROM "${tableName}"`);
  const totalRows = Number((countRow[0] as Record<string, unknown>)?.cnt ?? 0);
  const offset = (page - 1) * perPage;

  const rows = queryAll(
    db,
    `SELECT * FROM "${tableName}" ORDER BY "${sort}" ${order} LIMIT ? OFFSET ?`,
    [perPage, offset]
  );

  const { totalPages } = paginate(rows, page, perPage);

  const columns = columnNames.map((name) => {
    const col = colRows.find((c) => c.name === name);
    return {
      key: name,
      label: `${name}${col?.pk ? ' 🔑' : ''}`,
      sortable: true,
    };
  });

  return (
    <div>
      <div className="flex items-center gap-2 mb-4 text-sm text-gray-500">
        <Link href="/databases" className="hover:text-blue-600">{dbName}.db</Link>
        <span>/</span>
        <span className="font-medium text-gray-900">{tableName}</span>
      </div>
      <DataTable
        columns={columns}
        rows={rows}
        page={page}
        totalPages={totalPages}
        totalRows={totalRows}
        baseUrl={`/databases/${dbName}/${tableName}`}
        sort={sort}
        order={order}
      />
    </div>
  );
}
