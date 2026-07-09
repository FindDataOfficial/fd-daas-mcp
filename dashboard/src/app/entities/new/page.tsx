// @ts-nocheck
import Link from 'next/link';
import EntityCollectionForm from '@/components/entities/entity-collection-form';

export const dynamic = 'force-dynamic';

export default async function NewEntityCollectionPage() {
  const initial = {
    name: '',
    description: '',
    rule: '',
  };
  return (
    <div>
      <Link href="/entities" className="text-blue-600 hover:underline text-sm mb-4 inline-block">
        ← Back to entity collections
      </Link>
      <h1 className="text-2xl font-bold mb-6">New entity collection</h1>
      <EntityCollectionForm mode="create" initial={initial} />
    </div>
  );
}
