import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { privacyApi, sourcesApi } from '../lib/api';
import { PageHeader, Card, Button, Badge, Table, Empty } from '../components/ui';

export default function PrivacyPage() {
  const qc = useQueryClient();
  const { data: sources } = useQuery({ queryKey: ['sources'], queryFn: sourcesApi.list });
  const { data: findings } = useQuery({ queryKey: ['privacy'], queryFn: privacyApi.findings });
  const scan = useMutation({ mutationFn: (id: string) => privacyApi.scan(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['privacy'] }) });

  return (
    <div>
      <PageHeader title="Data Privacy" subtitle="PII discovery with Microsoft Presidio (per-source strategy)" />
      <Card className="p-5 mb-6">
        <h3 className="font-semibold mb-3">Run PII Scan</h3>
        {sources?.length ? sources.map((s: any) => (
          <div key={s.id} className="flex items-center justify-between border-b border-slate-100 py-2">
            <span>{s.name} <span className="text-slate-400 text-xs">({s.connector_type} · {s.category})</span></span>
            <Button variant="ghost" onClick={() => scan.mutate(s.id)} disabled={scan.isPending}>Scan PII</Button>
          </div>
        )) : <Empty message="Add a source first." />}
        {scan.data && <div className="mt-3 text-sm bg-slate-50 rounded-lg px-4 py-2">
          Strategy: <b>{scan.data.strategy}</b> · engine: {scan.data.engine} · columns: {scan.data.columns_scanned} · findings: {scan.data.findings}
        </div>}
      </Card>
      <Card className="p-5">
        <h3 className="font-semibold mb-3">PII Findings ({findings?.length ?? 0})</h3>
        {findings?.length ? (
          <Table head={['Detected Entity', 'Sensitivity', 'Confidence', 'When']}>
            {findings.map((f: any) => (
              <tr key={f.id} className="border-b border-slate-100">
                <td className="py-2 px-3"><Badge>{f.category}</Badge></td>
                <td className="py-2 px-3"><Badge>{f.sensitivity}</Badge></td>
                <td className="py-2 px-3">{f.confidence != null ? `${(f.confidence * 100).toFixed(0)}%` : '—'}</td>
                <td className="py-2 px-3 text-slate-500">{f.detected_at ? new Date(f.detected_at).toLocaleString() : ''}</td>
              </tr>
            ))}
          </Table>
        ) : <Empty message="No PII findings yet. Run a scan." />}
      </Card>
    </div>
  );
}
