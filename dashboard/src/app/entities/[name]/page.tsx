// @ts-nocheck
import { notFound } from 'next/navigation';
import { loadEntityCollectionDetail, loadEntityCollectionHistory } from '@/lib/entity-collections';
import EntityCollectionDetail from '@/components/entities/entity-collection-detail';

export const dynamic = 'force-dynamic';

interface PageProps {
  params: Promise<{ name: string }>;
}

export default async function EntityCollectionDetailPage({ params }: PageProps) {
  const { name } = await params;
  const decoded = decodeURIComponent(name);
  const collection = await loadEntityCollectionDetail(decoded);
  if (!collection) notFound();
  const history = await loadEntityCollectionHistory(decoded, null, 100);
  return (
    <EntityCollectionDetail collection={collection} initialHistory={history} />
  );
}
