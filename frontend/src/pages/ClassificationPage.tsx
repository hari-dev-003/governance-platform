import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { classificationApi, sourcesApi } from '../lib/api';
import { PageHeader, Card, Button, Badge, Table, Empty } from '../components/ui';

export default function ClassificationPage() {
  const qc = useQueryClient();
  const { data: rules } = useQuery({ queryKey: ['clsrules'], queryFn: classificationApi.rules });
  const { data: results } = useQuery({ queryKey: ['clsresults'], queryFn: classificationApi.results });
  const { data: sources } = useQuery({ queryKey: ['sources'], queryFn: sourcesApi.list });
  const run = useMutation({ mutationFn: (sid: string) => classificationApi.run(sid),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['clsresults'] }) });

  return (
    <div>
      <PageHeader title="Data Classification" subtitle="Detect PII / PHI / PCI and assign sensitivity automatically" />
      <div className="grid md:grid-cols-2 gap-6">
        <Card className="p-5">
          <h3 className="font-semibold mb-3">Run Classification</h3>
          {sources?.length ? sources.map((s: any) => (
            <div key={s.id} className="flex items-center justify-between border-b border-slate-100 py-2">
              <span>{s.name} <span className="text-slate-400 text-xs">({s.connector_type})</span></span>
              <Button variant="ghost" onClick={() => run.mutate(s.id)} disabled={run.isPending}>Scan columns</Button>
            </div>
          )) : <Empty message="Add a source first." />}
        </Card>
        <Card className="p-5">
          <h3 className="font-semibold mb-3">Active Rules ({rules?.length ?? 0})</h3>
          <Table head={['Rule', 'Category', 'Sensitivity']}>
            {(rules ?? []).map((r: any) => (
              <tr key={r.id} className="border-b border-slate-100">
                <td className="py-2 px-3">{r.name} {r.is_system_rule && <span className="text-[10px] text-slate-400">system</span>}</td>
                <td className="py-2 px-3"><Badge>{r.category}</Badge></td>
                <td className="py-2 px-3"><Badge>{r.sensitivity_level}</Badge></td>
              </tr>
            ))}
          </Table>
        </Card>
      </div>
      <Card className="p-5 mt-6">
        <h3 className="font-semibold mb-3">Detections ({results?.length ?? 0})</h3>
        {results?.length ? (
          <Table head={['Category', 'Sensitivity', 'Confidence', 'Status', 'When']}>
            {results.map((r: any) => (
              <tr key={r.id} className="border-b border-slate-100">
                <td className="py-2 px-3"><Badge>{r.category}</Badge></td>
                <td className="py-2 px-3"><Badge>{r.sensitivity}</Badge></td>
                <td className="py-2 px-3">{(r.confidence * 100).toFixed(0)}%</td>
                <td className="py-2 px-3"><Badge>{r.review_status}</Badge></td>
                <td className="py-2 px-3 text-slate-500">{r.detected_at ? new Date(r.detected_at).toLocaleString() : ''}</td>
              </tr>
            ))}
          </Table>
        ) : <Empty message="No detections yet. Run a scan." />}
      </Card>
    </div>
  );
}
