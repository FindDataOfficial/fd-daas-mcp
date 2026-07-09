// @ts-nocheck
import { notFound } from 'next/navigation';
import Link from 'next/link';
import {
  loadIndicatorCollectionDetail,
  loadIndicatorCollectionHistory,
  listIndicatorNames,
} from '@/lib/indicator-scores';
import IndicatorCollectionDetail from '@/components/indicators/indicator-collection-detail';

export const dynamic = 'force-dynamic';

interface PageProps {
  params: Promise<{ name: string }>;
}

export default async function IndicatorCollectionDetailPage({ params }: PageProps) {
  const { name } = await params;
  const decoded = decodeURIComponent(name);
  const collection = await loadIndicatorCollectionDetail(decoded);
  if (!collection) notFound();
  const [history, indicatorNames] = await Promise.all([
    loadIndicatorCollectionHistory(decoded, null, 100),
    listIndicatorNames(),
  ]);
  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <Link
            href="/process/indicators/collections"
            className="text-sm text-gray-600 hover:underline"
          >
            ← Collections
          </Link>
          <h1 className="text-2xl font-bold mt-1">{collection.name}</h1>
          {collection.description && (
            <p className="text-sm text-gray-500 mt-1">{collection.description}</p>
          )}
        </div>
      </div>
      <IndicatorCollectionDetail
        collection={collection}
        initialHistory={history}
        indicatorNames={indicatorNames}
      />
    </div>
  );
}
