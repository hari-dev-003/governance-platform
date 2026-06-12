import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { monitoringApi } from '../lib/api';
import { PageHeader, Card, Button, Badge, Table, Empty } from '../components/ui';

// demo reference vs (drifted) current datasets
const REF = Array.from({ length: 100 }, (_, i) => ({ income: 40 + (i % 30), age: 30 + (i % 25), score: (i % 50) / 50 }));
const CUR = Array.from({ length: 100 }, (_, i) => ({ income: 70 + (i % 40), age: 31 + (i % 25), score: (i % 50) / 50 }));

export default function MonitoringPage() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ['alerts'], queryFn: monitoringApi.alerts });
  const ack = useMutation({ mutationFn: (id: string) => monitoringApi.acknowledge(id), onSuccess: () => qc.invalidateQueries({ queryKey: ['alerts'] }) });

  const [evi, setEvi] = useState<any>(null);
  const runEvidently = useMutation({
    mutationFn: () => monitoringApi.evidentlyReport({ reference: REF, current: CUR }),
    onSuccess: (r) => { setEvi(r); qc.invalidateQueries({ queryKey: ['alerts'] }); },
  });
  const [ks, setKs] = useState<any>(null);
  const runKs = useMutation({
    mutationFn: () => monitoringApi.driftCheck({
      model_version_id: '00000000-0000-0000-0000-000000000000', feature: 'income',
      baseline: REF.map((r) => r.income), current: CUR.map((r) => r.income),
    }),
    onSuccess: (r) => { setKs(r); qc.invalidateQueries({ queryKey: ['alerts'] }); },
  });

  const [sweep, setSweep] = useState<any>(null);
  const runAll = useMutation({
    mutationFn: () => monitoringApi.runAll(),
    onSuccess: (r) => { setSweep(r); qc.invalidateQueries({ queryKey: ['alerts'] }); },
  });

  return (
    <div>
      <PageHeader title="Model Monitoring" subtitle="Evidently AI reports + alibi-detect drift detection"
        actions={
          <div className="flex items-center gap-3">
            {sweep && <span className="text-xs text-slate-500">swept {sweep.checked}/{sweep.active_configs} · {sweep.alerts_raised} alert(s)</span>}
            <Button variant="ghost" onClick={() => runAll.mutate()} disabled={runAll.isPending}>{runAll.isPending ? 'Running…' : 'Run all monitors'}</Button>
          </div>
        } />
      <div className="grid md:grid-cols-2 gap-6 mb-6">
        <Card className="p-5">
          <h3 className="font-semibold mb-1">Evidently AI - Data Drift Report</h3>
          <p className="text-xs text-slate-500 mb-3">Reference vs current dataset (demo).</p>
          <Button onClick={() => runEvidently.mutate()} disabled={runEvidently.isPending}>{runEvidently.isPending ? 'Running...' : 'Run Evidently Report'}</Button>
          {evi && (
            <div className="mt-3 text-sm">
              <div className="flex items-center gap-2 mb-2">engine: <Badge>{evi.engine}</Badge>
                {evi.dataset_drift != null && <Badge>{evi.dataset_drift ? 'DRIFT' : 'stable'}</Badge>}</div>
              {evi.per_column?.length ? (
                <Table head={['Column', 'Drift', 'Score', 'Test']}>
                  {evi.per_column.map((c: any) => (
                    <tr key={c.column} className="border-b border-slate-100">
                      <td className="py-1 px-3">{c.column}</td>
                      <td className="py-1 px-3">{c.drift_detected ? <Badge>fail</Badge> : <Badge>pass</Badge>}</td>
                      <td className="py-1 px-3">{c.drift_score}</td>
                      <td className="py-1 px-3 text-slate-500">{c.stattest}</td>
                    </tr>
                  ))}
                </Table>
              ) : evi.engine === 'unavailable' ? <p className="text-amber-600">Evidently not installed on backend.</p> : null}
            </div>
          )}
        </Card>
        <Card className="p-5">
          <h3 className="font-semibold mb-1">alibi-detect - KS Drift Test</h3>
          <p className="text-xs text-slate-500 mb-3">Univariate drift on the "income" feature (demo).</p>
          <Button onClick={() => runKs.mutate()} disabled={runKs.isPending}>Run KS Drift Check</Button>
          {ks && (
            <div className="mt-3 text-sm space-y-1">
              <div className="flex items-center gap-2">engine: <Badge>{ks.engine}</Badge> verdict: <Badge>{ks.drift ? (ks.severity || 'drift') : 'stable'}</Badge></div>
              {ks.ks_distance != null && <div>KS distance: {ks.ks_distance} · p-value: {ks.p_value}</div>}
              <div>PSI: {ks.psi}</div>
            </div>
          )}
        </Card>
      </div>
      <Card className="p-5">
        <h3 className="font-semibold mb-3">Drift Alerts</h3>
        {data?.length ? (
          <Table head={['Type', 'Severity', 'Features', 'Metrics', 'Status', 'Detected', '']}>
            {data.map((a: any) => (
              <tr key={a.id} className="border-b border-slate-100">
                <td className="py-2 px-3">{a.drift_type}</td>
                <td className="py-2 px-3"><Badge>{a.severity}</Badge></td>
                <td className="py-2 px-3">{(a.affected_features ?? []).join(', ')}</td>
                <td className="py-2 px-3 text-xs text-slate-500">{a.detection_metrics?.engine ?? ''}</td>
                <td className="py-2 px-3"><Badge>{a.status}</Badge></td>
                <td className="py-2 px-3 text-slate-500">{a.detected_at ? new Date(a.detected_at).toLocaleString() : ''}</td>
                <td className="py-2 px-3">{a.status === 'open' && <Button variant="ghost" onClick={() => ack.mutate(a.id)}>Ack</Button>}</td>
              </tr>
            ))}
          </Table>
        ) : <Empty message="No drift alerts yet. Run a check above." />}
      </Card>
    </div>
  );
}
