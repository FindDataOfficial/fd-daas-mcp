import { loadCollections } from '@/lib/collections';
import CollectionManager from '@/components/collections/collection-manager';

export const dynamic = 'force-dynamic';

export default async function CollectionsManagePage() {
  const collections = await loadCollections();
  return <CollectionManager collections={collections} />;
}
