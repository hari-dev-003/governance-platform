import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { modelsApi, sourcesApi } from '../lib/api';
import { PageHeader, Card, Button, Badge, Table, Empty } from '../components/ui';

export default function ModelRegistryPage() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ['models'], queryFn: modelsApi.list });
  const { data: sources } = useQuery({ queryKey: ['sources'], queryFn: sourcesApi.list });
  const registries = (sources ?? []).filter((s: any) => s.category === 'model_registry');
  const [show, setShow] = useState(false);
  const [syncSrc, setSyncSrc] = useState('');
  const [msg, setMsg] = useState('');
  const [form, setForm] = useState({ name: '', model_type: 'classification', framework: 'sklearn', business_domain: '', use_case: '' });
  const create = useMutation({ mutationFn: () => modelsApi.create(form),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['models'] }); setShow(false); } });
  const sync = useMutation({ mutationFn: () => modelsApi.sync(syncSrc),
    onSuccess: (r: any) => { setMsg(`Synced ${r.models_synced} model(s) and ${r.versions_synced} version(s) from the registry.`); qc.invalidateQueries({ queryKey: ['models'] }); } });
  return (
    <div>
      <PageHeader title="AI Model Registry" subtitle="Inventory, versioning, and EU AI Act risk classification"
        actions={
          <div className="flex gap-2 items-center">
            {registries.length > 0 && (
              <>
                <select value={syncSrc} onChange={(e) => setSyncSrc(e.target.value)} className="border border-slate-300 rounded-lg px-2 py-2 text-sm">
                  <option value="">registry source…</option>
                  {registries.map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
                <Button variant="ghost" onClick={() => sync.mutate()} disabled={!syncSrc || sync.isPending}>{sync.isPending ? 'Syncing…' : 'Sync from registry'}</Button>
              </>
            )}
            <Button onClick={() => setShow((s) => !s)}>{show ? 'Cancel' : '+ Register Model'}</Button>
          </div>
        } />
      {msg && <div className="mb-4 text-sm bg-emerald-50 text-emerald-800 border border-emerald-200 rounded-lg px-4 py-2">{msg}</div>}
      {show && (
        <Card className="p-5 mb-6 grid md:grid-cols-2 gap-3">
          <input placeholder="Model name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="border border-slate-300 rounded-lg px-3 py-2" />
          <input placeholder="Business domain" value={form.business_domain} onChange={(e) => setForm({ ...form, business_domain: e.target.value })} className="border border-slate-300 rounded-lg px-3 py-2" />
          <select value={form.model_type} onChange={(e) => setForm({ ...form, model_type: e.target.value })} className="border border-slate-300 rounded-lg px-3 py-2">
            {['classification', 'regression', 'nlp', 'cv', 'llm'].map((t) => <option key={t}>{t}</option>)}
          </select>
          <input placeholder="Framework" value={form.framework} onChange={(e) => setForm({ ...form, framework: e.target.value })} className="border border-slate-300 rounded-lg px-3 py-2" />
          <input placeholder="Use case" value={form.use_case} onChange={(e) => setForm({ ...form, use_case: e.target.value })} className="border border-slate-300 rounded-lg px-3 py-2 md:col-span-2" />
          <div className="md:col-span-2"><Button onClick={() => create.mutate()} disabled={!form.name}>Register</Button></div>
        </Card>
      )}
      <Card className="p-5">
        {data?.length ? (
          <Table head={['Model', 'Type', 'Framework', 'Domain', 'Risk Tier', 'Deployment']}>
            {data.map((m: any) => (
              <tr key={m.id} className="border-b border-slate-100">
                <td className="py-2 px-3"><Link to={`/ai-models/${m.id}`} className="text-brand-600 font-medium hover:underline">{m.name}</Link></td>
                <td className="py-2 px-3">{m.model_type}</td>
                <td className="py-2 px-3">{m.framework}</td>
                <td className="py-2 px-3">{m.business_domain ?? '—'}</td>
                <td className="py-2 px-3"><Badge>{m.risk_tier}</Badge></td>
                <td className="py-2 px-3"><Badge>{m.deployment_status}</Badge></td>
              </tr>
            ))}
          </Table>
        ) : <Empty message="No models registered yet." />}
      </Card>
    </div>
  );
}
