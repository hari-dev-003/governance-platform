import { useState, useEffect, useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { assetsApi, qualityApi } from '../lib/api';
import { PageHeader, Card, Badge, Button, Table, Empty } from '../components/ui';

type Tab = 'overview' | 'columns' | 'lineage' | 'quality' | 'preview' | 'governance';
const TABS: [Tab, string][] = [
  ['overview', 'Overview'], ['columns', 'Columns'], ['lineage', 'Lineage'],
  ['quality', 'Quality'], ['preview', 'Data Preview'], ['governance', 'Governance'],
];

export default function AssetDetailPage() {
  const { id = '' } = useParams();
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>('overview');

  const { data: asset } = useQuery({ queryKey: ['asset', id], queryFn: () => assetsApi.get(id) });
  const { data: columns } = useQuery({ queryKey: ['cols', id], queryFn: () => assetsApi.columns(id), enabled: !!asset });
  const { data: cls } = useQuery({ queryKey: ['cls', id], queryFn: () => assetsApi.classifications(id), enabled: !!asset });
  const { data: lineage } = useQuery({ queryKey: ['alin', id], queryFn: () => assetsApi.lineage(id), enabled: tab === 'lineage' });
  const { data: runs } = useQuery({ queryKey: ['qruns', id], queryFn: () => qualityApi.runs(id), enabled: tab === 'quality' });
  const { data: sample } = useQuery({ queryKey: ['samp', id], queryFn: () => assetsApi.sample(id), enabled: tab === 'preview' });

  const piiByCol = useMemo(() => {
    const m: Record<string, any> = {};
    (cls ?? []).forEach((c: any) => { if (!m[c.column] || c.confidence > m[c.column].confidence) m[c.column] = c; });
    return m;
  }, [cls]);

  if (!asset) return <Empty message="Loading…" />;
  const md = asset.technical_metadata || {};

  return (
    <div>
      <PageHeader title={asset.name}
        subtitle={`${asset.asset_type}${md.data_type ? ` · ${md.data_type}` : ''}${md.row_count != null ? ` · ${Number(md.row_count).toLocaleString()} rows` : ''}`}
        actions={<Link to="/catalog"><Button variant="ghost">← Catalog</Button></Link>} />

      <div className="flex flex-wrap gap-2 items-center mb-4">
        <Badge>{asset.sensitivity_level}</Badge>
        {asset.quality_score != null && <span className="text-sm text-slate-600">Quality: <b>{asset.quality_score.toFixed(0)}%</b></span>}
        {asset.domain && <span className="text-sm text-slate-600">Domain: <b>{asset.domain}</b></span>}
        {(asset.tags ?? []).map((t: string) => <span key={t} className="text-xs bg-slate-100 px-2 py-0.5 rounded">{t}</span>)}
      </div>

      <div className="flex gap-1 border-b border-slate-200 mb-5">
        {TABS.map(([k, label]) => (
          <button key={k} onClick={() => setTab(k)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px ${tab === k ? 'border-brand-600 text-brand-600' : 'border-transparent text-slate-500 hover:text-slate-700'}`}>{label}</button>
        ))}
      </div>

      {tab === 'overview' && (
        <div className="grid md:grid-cols-3 gap-6">
          <Card className="p-5 md:col-span-2">
            <h3 className="font-semibold mb-2">Description</h3>
            <p className="text-sm text-slate-600 mb-4">{asset.business_description || <span className="text-slate-400">No description yet — add one in Governance.</span>}</p>
            <h3 className="font-semibold mb-2">Properties</h3>
            <table className="text-sm w-full">
              <tbody>
                {[['Type', asset.asset_type], ['Fully-qualified name', md.external_id || asset.name],
                  ['Row count', md.row_count != null ? Number(md.row_count).toLocaleString() : '—'],
                  ['Last analyzed', md.last_analyzed || '—'], ['Sensitivity', asset.sensitivity_level]].map(([k, v]: any) => (
                  <tr key={k} className="border-b border-slate-100"><td className="py-1.5 text-slate-500 w-48">{k}</td><td className="py-1.5">{String(v)}</td></tr>
                ))}
              </tbody>
            </table>
          </Card>
          <Card className="p-5">
            <h3 className="font-semibold mb-2">Classification</h3>
            {cls?.length ? (
              <ul className="space-y-1 text-sm">
                {cls.slice(0, 12).map((c: any, i: number) => (
                  <li key={i} className="flex justify-between border-b border-slate-100 py-1">
                    <span>{c.column}</span><Badge>{c.category}</Badge></li>
                ))}
              </ul>
            ) : <Empty message="No PII/classification findings" />}
          </Card>
        </div>
      )}

      {tab === 'columns' && (
        <Card className="p-5">
          <h3 className="font-semibold mb-3">Columns ({columns?.length ?? 0})</h3>
          {columns?.length ? (
            <Table head={['Column', 'Type', 'Nullable', 'Classification', 'Sensitivity']}>
              {columns.map((c: any) => {
                const pii = piiByCol[c.name];
                return (
                  <tr key={c.id} className="border-b border-slate-100">
                    <td className="py-2 px-3"><Link to={`/catalog/${c.id}`} className="text-brand-600 hover:underline">{c.name}</Link></td>
                    <td className="py-2 px-3 text-slate-600">{c.technical_metadata?.data_type ?? '—'}</td>
                    <td className="py-2 px-3">{c.technical_metadata?.is_nullable ?? '—'}</td>
                    <td className="py-2 px-3">{pii ? <Badge>{pii.category}</Badge> : <span className="text-slate-400">—</span>}</td>
                    <td className="py-2 px-3"><Badge>{c.sensitivity_level}</Badge></td>
                  </tr>
                );
              })}
            </Table>
          ) : <Empty message="No columns (this asset has no children)." />}
        </Card>
      )}

      {tab === 'lineage' && <LineageTab id={id} lineage={lineage} />}

      {tab === 'quality' && (
        <Card className="p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold">Quality runs</h3>
            <Link to="/quality"><Button variant="ghost">Manage rules →</Button></Link>
          </div>
          {runs?.length ? (
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
          ) : <Empty message="No quality runs yet. Add rules on the Quality page." />}
        </Card>
      )}

      {tab === 'preview' && (
        <Card className="p-5">
          <h3 className="font-semibold mb-3">Data preview</h3>
          {sample?.columns?.length ? (
            <div className="overflow-x-auto">
              <table className="text-xs w-full">
                <thead><tr className="bg-slate-50">{sample.columns.map((c: string) => <th key={c} className="py-1.5 px-2 text-left font-medium border-b">{c}</th>)}</tr></thead>
                <tbody>{sample.rows.map((row: string[], i: number) => (
                  <tr key={i} className="border-b border-slate-100">{row.map((v, j) => <td key={j} className="py-1 px-2 text-slate-600 truncate max-w-[160px]">{v}</td>)}</tr>
                ))}</tbody>
              </table>
            </div>
          ) : <Empty message={sample?.error ? `Preview unavailable: ${sample.error}` : 'No preview available for this asset type.'} />}
        </Card>
      )}

      {tab === 'governance' && <GovernanceTab id={id} asset={asset} onSaved={() => qc.invalidateQueries({ queryKey: ['asset', id] })} />}
    </div>
  );
}

function LineageTab({ id, lineage }: any) {
  const center = (lineage?.nodes ?? []).find((n: any) => n.is_center);
  const byId: Record<string, any> = {};
  (lineage?.nodes ?? []).forEach((n: any) => { byId[n.id] = n; });
  const up = (lineage?.edges ?? []).filter((e: any) => e.target === id).map((e: any) => byId[e.source]).filter(Boolean);
  const down = (lineage?.edges ?? []).filter((e: any) => e.source === id).map((e: any) => byId[e.target]).filter(Boolean);
  return (
    <div className="grid md:grid-cols-3 gap-6">
      <Card className="p-5"><h3 className="font-semibold mb-3">Upstream ({up.length})</h3>
        {up.length ? up.map((n: any) => <Link key={n.id} to={`/catalog/${n.id}`} className="block py-1 text-sm text-brand-600 hover:underline">{n.name}</Link>) : <Empty message="None" />}</Card>
      <Card className="p-5 border-brand-300"><h3 className="font-semibold mb-3">{center?.name ?? 'This asset'}</h3>
        <p className="text-sm text-slate-500">Upstream feeds in, downstream consumes. See full graph on the Lineage page.</p>
        <Link to="/lineage"><Button variant="ghost">Open lineage graph →</Button></Link></Card>
      <Card className="p-5"><h3 className="font-semibold mb-3">Downstream ({down.length})</h3>
        {down.length ? down.map((n: any) => <Link key={n.id} to={`/catalog/${n.id}`} className="block py-1 text-sm text-brand-600 hover:underline">{n.name}</Link>) : <Empty message="None" />}</Card>
    </div>
  );
}

function GovernanceTab({ id, asset, onSaved }: any) {
  const [desc, setDesc] = useState(asset.business_description ?? '');
  const [domain, setDomain] = useState(asset.domain ?? '');
  const [sens, setSens] = useState(asset.sensitivity_level ?? 'unclassified');
  useEffect(() => { setDesc(asset.business_description ?? ''); setDomain(asset.domain ?? ''); setSens(asset.sensitivity_level ?? 'unclassified'); }, [asset]);
  const save = useMutation({ mutationFn: () => assetsApi.update(id, { business_description: desc, domain, sensitivity_level: sens }), onSuccess: onSaved });
  return (
    <Card className="p-5 max-w-2xl">
      <h3 className="font-semibold mb-3">Governance metadata</h3>
      <label className="text-sm text-slate-500">Description</label>
      <textarea value={desc} onChange={(e) => setDesc(e.target.value)} rows={3} className="w-full border border-slate-300 rounded-lg px-3 py-2 mb-3" />
      <div className="grid grid-cols-2 gap-3 mb-3">
        <div><label className="text-sm text-slate-500">Domain</label>
          <input value={domain} onChange={(e) => setDomain(e.target.value)} className="w-full border border-slate-300 rounded-lg px-3 py-2" /></div>
        <div><label className="text-sm text-slate-500">Sensitivity</label>
          <select value={sens} onChange={(e) => setSens(e.target.value)} className="w-full border border-slate-300 rounded-lg px-3 py-2">
            {['unclassified', 'public', 'internal', 'confidential', 'restricted'].map((s) => <option key={s}>{s}</option>)}
          </select></div>
      </div>
      <Button onClick={() => save.mutate()} disabled={save.isPending}>{save.isPending ? 'Saving…' : 'Save'}</Button>
    </Card>
  );
}
