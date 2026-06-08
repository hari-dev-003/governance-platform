import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { assetsApi, qualityApi } from '../lib/api';
import { PageHeader, Card, Badge, Button, Table, Empty } from '../components/ui';

export default function AssetDetailPage() {
  const { id = '' } = useParams();
  const qc = useQueryClient();
  const { data: asset } = useQuery({ queryKey: ['asset', id], queryFn: () => assetsApi.get(id) });
  const { data: columns } = useQuery({ queryKey: ['cols', id], queryFn: () => assetsApi.columns(id) });
  const { data: runs } = useQuery({ queryKey: ['qruns', id], queryFn: () => qualityApi.runs(id) });

  const [desc, setDesc] = useState('');
  const [domain, setDomain] = useState('');
  const [sens, setSens] = useState('');
  useEffect(() => { if (asset) { setDesc(asset.business_description ?? ''); setDomain(asset.domain ?? ''); setSens(asset.sensitivity_level ?? ''); } }, [asset]);

  const save = useMutation({
    mutationFn: () => assetsApi.update(id, { business_description: desc, domain, sensitivity_level: sens }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['asset', id] }),
  });
  const runQuality = useMutation({ mutationFn: () => qualityApi.run(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['qruns', id] }); qc.invalidateQueries({ queryKey: ['asset', id] }); } });

  if (!asset) return <Empty message="Loading…" />;
  return (
    <div>
      <PageHeader title={asset.name} subtitle={`${asset.asset_type} · ${asset.technical_metadata?.data_type ?? ''}`}
        actions={<Link to="/catalog"><Button variant="ghost">← Catalog</Button></Link>} />
      <div className="grid md:grid-cols-3 gap-6">
        <Card className="p-5 md:col-span-2">
          <h3 className="font-semibold mb-3">Business Metadata</h3>
          <label className="text-sm text-slate-500">Description</label>
          <textarea value={desc} onChange={(e) => setDesc(e.target.value)} className="w-full border border-slate-300 rounded-lg px-3 py-2 mb-3" rows={3} />
          <div className="grid grid-cols-2 gap-3 mb-3">
            <div><label className="text-sm text-slate-500">Domain</label>
              <input value={domain} onChange={(e) => setDomain(e.target.value)} className="w-full border border-slate-300 rounded-lg px-3 py-2" /></div>
            <div><label className="text-sm text-slate-500">Sensitivity</label>
              <select value={sens} onChange={(e) => setSens(e.target.value)} className="w-full border border-slate-300 rounded-lg px-3 py-2">
                {['unclassified', 'public', 'internal', 'confidential', 'restricted'].map((s) => <option key={s}>{s}</option>)}
              </select></div>
          </div>
          <Button onClick={() => save.mutate()}>Save</Button>
        </Card>
        <Card className="p-5">
          <h3 className="font-semibold mb-3">Governance</h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between"><span className="text-slate-500">Sensitivity</span><Badge>{asset.sensitivity_level}</Badge></div>
            <div className="flex justify-between"><span className="text-slate-500">Quality</span><span>{asset.quality_score != null ? `${asset.quality_score.toFixed(0)}%` : '—'}</span></div>
            <div className="flex justify-between"><span className="text-slate-500">Deprecated</span><span>{asset.is_deprecated ? 'Yes' : 'No'}</span></div>
          </div>
          <div className="mt-4"><Button variant="ghost" onClick={() => runQuality.mutate()}>Run Quality Checks</Button></div>
        </Card>
      </div>

      {columns && columns.length > 0 && (
        <Card className="p-5 mt-6">
          <h3 className="font-semibold mb-3">Columns ({columns.length})</h3>
          <Table head={['Name', 'Type', 'Sensitivity']}>
            {columns.map((c: any) => (
              <tr key={c.id} className="border-b border-slate-100">
                <td className="py-2 px-3"><Link to={`/catalog/${c.id}`} className="text-brand-600 hover:underline">{c.name}</Link></td>
                <td className="py-2 px-3">{c.technical_metadata?.data_type ?? '—'}</td>
                <td className="py-2 px-3"><Badge>{c.sensitivity_level}</Badge></td>
              </tr>
            ))}
          </Table>
        </Card>
      )}

      {runs && runs.length > 0 && (
        <Card className="p-5 mt-6">
          <h3 className="font-semibold mb-3">Quality Runs</h3>
          <Table head={['Score', 'Passed', 'Failed', 'When']}>
            {runs.map((r: any) => (
              <tr key={r.id} className="border-b border-slate-100">
                <td className="py-2 px-3">{r.overall_score != null ? `${r.overall_score.toFixed(0)}%` : '—'}</td>
                <td className="py-2 px-3 text-green-600">{r.passed_rules}</td>
                <td className="py-2 px-3 text-red-600">{r.failed_rules}</td>
                <td className="py-2 px-3 text-slate-500">{r.run_at ? new Date(r.run_at).toLocaleString() : ''}</td>
              </tr>
            ))}
          </Table>
        </Card>
      )}
    </div>
  );
}
