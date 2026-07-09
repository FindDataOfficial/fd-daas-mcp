// @ts-nocheck
import Link from 'next/link';
import AgentForm from '../agent-form';
import { getAgentOptions } from '../server-data';

export default async function NewAgentPage() {
  const options = await getAgentOptions();

  const initial = {
    name: '',
    upstream: '',
    role: '',
    goal: '',
    backstory: '',
    model: '',
    enabled: true,
  };

  return (
    <div>
      <Link href="/agents" className="text-blue-600 hover:underline text-sm mb-4 inline-block">
        ← Back to agents
      </Link>
      <h1 className="text-2xl font-bold mb-6">New specialist agent</h1>
      <AgentForm mode="create" initial={initial} options={options} />
    </div>
  );
}
