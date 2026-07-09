// @ts-nocheck
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { loadEntityCollectionDetail } from '@/lib/entity-collections';
import EntityCollectionForm from '@/components/entities/entity-collection-form';

export const dynamic = 'force-dynamic';

interface PageProps {
  params: Promise<{ name: string }>;
}

export default async function EditEntityCollectionPage({ params }: PageProps) {
  const { name } = await params;
  const decoded = decodeURIComponent(name);
  const collection = await loadEntityCollectionDetail(decoded);
  if (!collection) notFound();
  const initial = {
    name: collection.name,
    description: collection.description || '',
    rule: collection.rule ? JSON.stringify(collection.rule) : '',
  };
  return (
    <div>
      <Link href={`/entities/${encodeURIComponent(decoded)}`} className="text-blue-600 hover:underline text-sm mb-4 inline-block">
        ← Back to {decoded}
      </Link>
      <h1 className="text-2xl font-bold mb-6">Edit entity collection</h1>
      <EntityCollectionForm mode="edit" initial={initial} />
    </div>
  );
}
