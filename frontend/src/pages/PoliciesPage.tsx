import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { policiesApi } from '../lib/api';
import { PageHeader, Card, Button, Badge, Table, Empty } from '../components/ui';

export default function PoliciesPage() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ['policies'], queryFn: policiesApi.list });
  const [show, setShow] = useState(false);
  const [form, setForm] = useState({ name: '', policy_type: 'access', rule: '' });
  const create = useMutation({
    mutationFn: () => policiesApi.create({ name: form.name, policy_type: form.policy_type, rules: { description: form.rule } }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['policies'] }); setShow(false); },
  });
  return (
    <div>
      <PageHeader title="Data Policies" subtitle="Access · retention · masking · usage-purpose rules"
        actions={<Button onClick={() => setShow((s) => !s)}>{show ? 'Cancel' : '+ New Policy'}</Button>} />
      {show && (
        <Card className="p-5 mb-6 space-y-3">
          <input placeholder="Policy name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="w-full border border-slate-300 rounded-lg px-3 py-2" />
          <select value={form.policy_type} onChange={(e) => setForm({ ...form, policy_type: e.target.value })} className="w-full border border-slate-300 rounded-lg px-3 py-2">
            {['access', 'retention', 'masking', 'usage_purpose'].map((t) => <option key={t}>{t}</option>)}
          </select>
          <textarea placeholder="Rule description" value={form.rule} onChange={(e) => setForm({ ...form, rule: e.target.value })} className="w-full border border-slate-300 rounded-lg px-3 py-2" rows={2} />
          <Button onClick={() => create.mutate()} disabled={!form.name}>Create</Button>
        </Card>
      )}
      <Card className="p-5">
        {data?.length ? (
          <Table head={['Name', 'Type', 'Active']}>
            {data.map((p: any) => (
              <tr key={p.id} className="border-b border-slate-100">
                <td className="py-2 px-3 font-medium">{p.name}</td>
                <td className="py-2 px-3"><Badge>{p.policy_type}</Badge></td>
                <td className="py-2 px-3">{p.is_active ? 'Yes' : 'No'}</td>
              </tr>
            ))}
          </Table>
        ) : <Empty message="No policies yet." />}
      </Card>
    </div>
  );
}
