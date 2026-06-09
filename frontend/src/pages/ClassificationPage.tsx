import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { classificationApi, privacyApi, sourcesApi } from '../lib/api';
import { PageHeader, Card, Button, Badge, Table, Empty } from '../components/ui';

export default function ClassificationPage() {
  const qc = useQueryClient();
  const { data: rules } = useQuery({ queryKey: ['clsrules'], queryFn: classificationApi.rules });
  const { data: sources } = useQuery({ queryKey: ['sources'], queryFn: sourcesApi.list });
  const { data: runs } = useQuery({ queryKey: ['clsruns'], queryFn: classificationApi.runs });

  const [runId, setRunId] = useState<string>('');
  // default to most recent run
  useEffect(() => { if (runs?.length && !runId) setRunId(runs[0].id); }, [runs, runId]);
  const { data: findings } = useQuery({
    queryKey: ['clsfindings', runId], queryFn: () => classificationApi.runFindings(runId), enabled: !!runId,
  });

  const classify = useMutation({
    mutationFn: (sid: string) => classificationApi.run(sid),
    onSuccess: (r: any) => { setRunId(r.run_id); qc.invalidateQueries({ queryKey: ['clsruns'] }); },
  });
  const detectPii = useMutation({
    mutationFn: (sid: string) => privacyApi.scan(sid),
    onSuccess: (r: any) => { setRunId(r.run_id); qc.invalidateQueries({ queryKey: ['clsruns'] }); },
  });

  const sel = runs?.find((r: any) => r.id === runId);
  const runLabel = (r: any) =>
    `${r.scan_type === 'privacy' ? 'Privacy/Presidio' : 'Classification/rules'} · ${r.total_findings} findings · ${r.started_at ? new Date(r.started_at).toLocaleString() : ''}`;

  return (
    <div>
      <PageHeader title="Classification & Privacy" subtitle="Rule-based classification and Presidio PII detection — grouped by run" />

      <div className="grid md:grid-cols-2 gap-6 mb-6">
        <Card className="p-5">
          <h3 className="font-semibold mb-3">Run a scan</h3>
          {sources?.length ? sources.map((s: any) => (
            <div key={s.id} className="flex items-center justify-between border-b border-slate-100 py-2">
              <span>{s.name} <span className="text-slate-400 text-xs">({s.connector_type})</span></span>
              <div className="flex gap-2">
                <Button variant="ghost" onClick={() => classify.mutate(s.id)} disabled={classify.isPending}>Classify (rules)</Button>
                <Button variant="ghost" onClick={() => detectPii.mutate(s.id)} disabled={detectPii.isPending}>Detect PII (Presidio)</Button>
              </div>
            </div>
          )) : <Empty message="Add a source first." />}
        </Card>
        <Card className="p-5">
          <h3 className="font-semibold mb-3">Active rules ({rules?.length ?? 0})</h3>
          <Table head={['Rule', 'Category', 'Sensitivity']}>
            {(rules ?? []).map((r: any) => (
              <tr key={r.id} className="border-b border-slate-100">
                <td className="py-1 px-3">{r.name} {r.is_system_rule && <span className="text-[10px] text-slate-400">system</span>}</td>
                <td className="py-1 px-3"><Badge>{r.category}</Badge></td>
                <td className="py-1 px-3"><Badge>{r.sensitivity_level}</Badge></td>
              </tr>
            ))}
          </Table>
        </Card>
      </div>

      <Card className="p-5">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-semibold">Findings by run</h3>
          <select value={runId} onChange={(e) => setRunId(e.target.value)} className="border border-slate-300 rounded-lg px-3 py-2 text-sm">
            {(runs ?? []).map((r: any) => <option key={r.id} value={r.id}>{runLabel(r)}</option>)}
          </select>
        </div>
        {sel && <div className="mb-3"><Badge>{sel.scan_type}</Badge> <span className="text-xs text-slate-500 ml-2">engine: {sel.engine} · columns scanned: {sel.columns_scanned}</span></div>}
        {findings?.length ? (
          <Table head={['Column', 'Detected', 'Sensitivity', 'Confidence', 'When']}>
            {findings.map((f: any) => (
              <tr key={f.id} className="border-b border-slate-100">
                <td className="py-1 px-3">{f.column}</td>
                <td className="py-1 px-3"><Badge>{f.category}</Badge></td>
                <td className="py-1 px-3"><Badge>{f.sensitivity}</Badge></td>
                <td className="py-1 px-3">{f.confidence != null ? `${(f.confidence * 100).toFixed(0)}%` : '—'}</td>
                <td className="py-1 px-3 text-slate-500">{f.detected_at ? new Date(f.detected_at).toLocaleString() : ''}</td>
              </tr>
            ))}
          </Table>
        ) : <Empty message={runId ? 'No findings in this run.' : 'Run a scan to see findings.'} />}
      </Card>
    </div>
  );
}
