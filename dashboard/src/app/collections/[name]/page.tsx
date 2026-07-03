import { notFound } from 'next/navigation';
import { loadCatalog, loadCollection, loadCollections } from '@/lib/collections';
import CollectionWorkspace from '@/components/collections/workspace';

export const dynamic = 'force-dynamic';

interface PageProps {
  params: Promise<{ name: string }>;
}

export default async function CollectionWorkspacePage({ params }: PageProps) {
  const { name } = await params;
  const decoded = decodeURIComponent(name);

  const [catalog, collection, collections] = await Promise.all([
    loadCatalog(),
    loadCollection(decoded),
    loadCollections(),
  ]);

  if (!collection) {
    notFound();
  }

  return (
    <CollectionWorkspace
      catalog={catalog}
      collection={collection}
      collections={collections}
    />
  );
}
