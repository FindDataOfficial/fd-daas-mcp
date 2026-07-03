import Link from 'next/link';
import { loadCollections } from '@/lib/collections';
import CollectionSwitcher from '@/components/collections/collection-switcher';

export const dynamic = 'force-dynamic';

export default async function CollectionsHomePage() {
  const collections = await loadCollections();
  return (
    <div className="h-full flex flex-col">
      <CollectionSwitcher collections={collections} activeName={null} />
      <div className="flex-1 flex items-center justify-center bg-gray-50">
        <div className="max-w-md text-center px-6">
          <h2 className="text-lg font-semibold mb-2">Datasource Collections</h2>
          <p className="text-sm text-gray-600 mb-4">
            Curate sets of datasources and sections, then chat against them.
            Pick a collection above or create a new one to get started.
          </p>
          {collections.length > 0 && (
            <ul className="text-left bg-white border rounded divide-y">
              {collections.map((c) => (
                <li key={c.id}>
                  <Link
                    href={`/collections/${encodeURIComponent(c.name)}`}
                    className="block px-4 py-2 hover:bg-blue-50 text-sm"
                  >
                    <div className="font-medium">{c.name}</div>
                    <div className="text-xs text-gray-500">
                      {c.item_count} item{c.item_count === 1 ? '' : 's'}
                      {c.description && <span> · {c.description}</span>}
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
