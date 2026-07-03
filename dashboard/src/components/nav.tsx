'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const LINKS = [
  { href: '/chat', label: 'Chat' },
  { href: '/collections', label: 'Collections' },
  { href: '/collections/manage', label: 'Manage' },
  { href: '/databases', label: 'Databases' },
  { href: '/cron', label: 'Cron Tasks' },
  { href: '/datasources', label: 'Datasources' },
  { href: '/settings', label: 'Settings' },
];

export default function Nav() {
  const pathname = usePathname();

  return (
    <nav className="w-56 bg-gray-900 text-gray-100 p-4 flex flex-col gap-1 shrink-0">
      <h1 className="text-lg font-bold mb-4">MCP Dashboard</h1>
      {LINKS.map((l) => (
        <Link
          key={l.href}
          href={l.href}
          className={`px-3 py-2 rounded text-sm ${
            pathname.startsWith(l.href)
              ? 'bg-gray-700 text-white'
              : 'hover:bg-gray-800 text-gray-300'
          }`}
        >
          {l.label}
        </Link>
      ))}
    </nav>
  );
}
