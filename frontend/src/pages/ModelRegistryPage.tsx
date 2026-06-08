import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { modelsApi } from '../lib/api';
import { PageHeader, Card, Button, Badge, Table, Empty } from '../components/ui';

export default function ModelRegistryPage() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ['models'], queryFn: modelsApi.list });
  const [show, setShow] = useState(false);
  const [form, setForm] = useState({ name: '', model_type: 'classification', framework: 'sklearn', business_domain: '', use_case: '' });
  const create = useMutation({ mutationFn: () => modelsApi.create(form),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['models'] }); setShow(false); } });
  return (
    <div>
      <PageHeader title="AI Model Registry" subtitle="Inventory, versioning, and EU AI Act risk classification"
        actions={<Button onClick={() => setShow((s) => !s)}>{show ? 'Cancel' : '+ Register Model'}</Button>} />
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
