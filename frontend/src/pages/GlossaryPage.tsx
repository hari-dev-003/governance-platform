import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { glossaryApi } from '../lib/api';
import { PageHeader, Card, Button, Badge, Table, Empty } from '../components/ui';

export default function GlossaryPage() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ['glossary'], queryFn: glossaryApi.list });
  const [show, setShow] = useState(false);
  const [form, setForm] = useState({ name: '', definition: '', domain: '' });

  const create = useMutation({ mutationFn: () => glossaryApi.create(form),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['glossary'] }); setShow(false); setForm({ name: '', definition: '', domain: '' }); } });
  const submit = useMutation({ mutationFn: (id: string) => glossaryApi.submit(id), onSuccess: () => qc.invalidateQueries({ queryKey: ['glossary'] }) });
  const approve = useMutation({ mutationFn: (id: string) => glossaryApi.approve(id), onSuccess: () => qc.invalidateQueries({ queryKey: ['glossary'] }) });

  return (
    <div>
      <PageHeader title="Business Glossary" subtitle="Shared definitions with a draft → approval workflow"
        actions={<Button onClick={() => setShow((s) => !s)}>{show ? 'Cancel' : '+ New Term'}</Button>} />
      {show && (
        <Card className="p-5 mb-6 space-y-3">
          <input placeholder="Term name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="w-full border border-slate-300 rounded-lg px-3 py-2" />
          <textarea placeholder="Definition" value={form.definition} onChange={(e) => setForm({ ...form, definition: e.target.value })} className="w-full border border-slate-300 rounded-lg px-3 py-2" rows={2} />
          <input placeholder="Domain" value={form.domain} onChange={(e) => setForm({ ...form, domain: e.target.value })} className="w-full border border-slate-300 rounded-lg px-3 py-2" />
          <Button onClick={() => create.mutate()} disabled={!form.name || !form.definition}>Create Draft</Button>
        </Card>
      )}
      <Card className="p-5">
        {data?.length ? (
          <Table head={['Term', 'Definition', 'Domain', 'Status', 'Actions']}>
            {data.map((t: any) => (
              <tr key={t.id} className="border-b border-slate-100">
                <td className="py-2 px-3 font-medium">{t.name}</td>
                <td className="py-2 px-3 text-slate-600 max-w-md">{t.definition}</td>
                <td className="py-2 px-3">{t.domain ?? '—'}</td>
                <td className="py-2 px-3"><Badge>{t.status}</Badge></td>
                <td className="py-2 px-3 flex gap-2">
                  {t.status === 'draft' && <Button variant="ghost" onClick={() => submit.mutate(t.id)}>Submit</Button>}
                  {t.status === 'pending_approval' && <Button onClick={() => approve.mutate(t.id)}>Approve</Button>}
                </td>
              </tr>
            ))}
          </Table>
        ) : <Empty message="No glossary terms yet." />}
      </Card>
    </div>
  );
}
