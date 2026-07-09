import { loadSourceScores, loadCollectionScores } from '@/lib/scores';
import { loadCollections } from '@/lib/collections';
import ScoresManager from '@/components/scores/scores-manager';

export const dynamic = 'force-dynamic';

export default async function ScoresPage() {
  const [sourceScores, collections] = await Promise.all([
    loadSourceScores(),
    loadCollections(),
  ]);

  // Default the collection picker to the first collection (if any) and
  // pre-load its items so the first paint isn't empty.
  const firstName = collections[0]?.name;
  const firstCollection =
    firstName != null ? await loadCollectionScores(firstName) : null;

  return (
    <ScoresManager
      sourceScores={sourceScores}
      collections={collections.map((c) => ({ id: c.id, name: c.name }))}
      initialCollection={firstCollection}
    />
  );
}
