import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { auditApi } from '../lib/api';
import { PageHeader, Card, Badge, Table, Empty } from '../components/ui';

export default function AuditPage() {
  const [action, setAction] = useState('');
  const { data } = useQuery({ queryKey: ['audit', action], queryFn: () => auditApi.logs({ action: action || undefined, limit: 300 }) });
  return (
    <div>
      <PageHeader title="Audit Trail" subtitle="Immutable, append-only record of every governance action" />
      <Card className="p-4 mb-4">
        <input placeholder="Filter by action (e.g. model.registered)" value={action} onChange={(e) => setAction(e.target.value)}
          className="border border-slate-300 rounded-lg px-3 py-2 w-full max-w-md" />
      </Card>
      <Card className="p-5">
        {data?.length ? (
          <Table head={['Action', 'Resource', 'Name', 'When']}>
            {data.map((a: any) => (
              <tr key={a.id} className="border-b border-slate-100">
                <td className="py-2 px-3"><Badge>{a.action?.split('.')[0]}</Badge> <span className="ml-2">{a.action}</span></td>
                <td className="py-2 px-3 text-slate-600">{a.resource_type ?? '—'}</td>
                <td className="py-2 px-3 text-slate-600">{a.resource_name ?? '—'}</td>
                <td className="py-2 px-3 text-slate-500">{a.occurred_at ? new Date(a.occurred_at).toLocaleString() : ''}</td>
              </tr>
            ))}
          </Table>
        ) : <Empty message="No audit entries yet." />}
      </Card>
    </div>
  );
}
