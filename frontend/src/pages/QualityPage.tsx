import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { assetsApi, qualityApi } from '../lib/api';
import { PageHeader, Card, Button, Badge, Table, Empty } from '../components/ui';

const RULE_TYPES = ['not_null', 'unique', 'regex', 'range', 'in_set'] as const;
const DIM: Record<string, string> = {
  not_null: 'completeness', unique: 'uniqueness', regex: 'validity', range: 'validity', in_set: 'validity',
};

export default function QualityPage() {
  const qc = useQueryClient();
  // /assets returns a paginated object { total, limit, offset, items }, not a bare array.
  const { data: tableRes } = useQuery({ queryKey: ['qtables'], queryFn: () => assetsApi.list({ type: 'table', limit: 200 }) });
  const tables = tableRes?.items ?? [];
  const [sel, setSel] = useState<any>(null);

  const { data: columns } = useQuery({ queryKey: ['qcols', sel?.id], queryFn: () => assetsApi.columns(sel.id), enabled: !!sel });
  const { data: rules } = useQuery({ queryKey: ['qrules', sel?.id], queryFn: () => qualityApi.rules(sel.id), enabled: !!sel });
  const { data: runs } = useQuery({ queryKey: ['qruns', sel?.id], queryFn: () => qualityApi.runs(sel.id), enabled: !!sel });

  const [form, setForm] = useState({ column: '', rule_type: 'not_null', pattern: '', min: '', max: '', values: '' });
  const [runMsg, setRunMsg] = useState('');

  const createRule = useMutation({
    mutationFn: () => {
      const cfg: any = { column: form.column };
      if (form.rule_type === 'regex') cfg.pattern = form.pattern;
      if (form.rule_type === 'range') { if (form.min !== '') cfg.min = Number(form.min); if (form.max !== '') cfg.max = Number(form.max); }
      if (form.rule_type === 'in_set') cfg.values = form.values.split(',').map((v) => v.trim()).filter(Boolean);
      return qualityApi.createRule({
        asset_id: sel.id, name: `${form.rule_type} ${form.column}`, dimension: DIM[form.rule_type],
        rule_type: form.rule_type, rule_config: cfg, severity: 'warning',
      });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['qrules', sel?.id] }),
  });

  const autogen = useMutation({
    mutationFn: () => qualityApi.autogenerate(sel.id),
    onSuccess: (r: any) => { setRunMsg(`Auto-generated ${r.created} rule(s) from profiling.`); qc.invalidateQueries({ queryKey: ['qrules', sel?.id] }); },
  });
  const run = useMutation({
    mutationFn: () => qualityApi.run(sel.id),
    onSuccess: (r: any) => {
      setRunMsg(r.message ? r.message : `engine=${r.engine} score=${r.score ?? '—'} passed=${r.passed} failed=${r.failed}`);
      qc.invalidateQueries({ queryKey: ['qruns', sel?.id] });
      qc.invalidateQueries({ queryKey: ['qtables'] });
    },
  });

  return (
    <div>
      <PageHeader title="Data Quality" subtitle="Define rules and run Great Expectations checks per table" />
      <div className="grid md:grid-cols-3 gap-6">
        <Card className="p-5">
          <h3 className="font-semibold mb-3">Tables</h3>
          {tables?.length ? tables.map((t: any) => (
            <button key={t.id} onClick={() => { setSel(t); setRunMsg(''); }}
              className={`w-full text-left px-3 py-2 rounded-lg text-sm flex justify-between ${sel?.id === t.id ? 'bg-brand-600 text-white' : 'hover:bg-slate-100'}`}>
              <span>{t.name}</span>
              <span>{t.quality_score != null ? `${t.quality_score.toFixed(0)}%` : '—'}</span>
            </button>
          )) : <Empty message="No tables. Scan a database source first." />}
        </Card>

        <Card className="p-5 md:col-span-2">
          {!sel ? <Empty message="Select a table to add and run quality rules." /> : (
            <>
              <h3 className="font-semibold mb-3">{sel.name} — rules</h3>
              {/* add rule */}
              <div className="grid grid-cols-2 gap-2 mb-3">
                <select value={form.column} onChange={(e) => setForm({ ...form, column: e.target.value })} className="border border-slate-300 rounded-lg px-3 py-2">
                  <option value="">column…</option>
                  {(columns ?? []).map((c: any) => <option key={c.id} value={c.name}>{c.name}</option>)}
                </select>
                <select value={form.rule_type} onChange={(e) => setForm({ ...form, rule_type: e.target.value })} className="border border-slate-300 rounded-lg px-3 py-2">
                  {RULE_TYPES.map((r) => <option key={r}>{r}</option>)}
                </select>
                {form.rule_type === 'regex' && <input placeholder="pattern" value={form.pattern} onChange={(e) => setForm({ ...form, pattern: e.target.value })} className="border border-slate-300 rounded-lg px-3 py-2 col-span-2" />}
                {form.rule_type === 'range' && <>
                  <input placeholder="min" value={form.min} onChange={(e) => setForm({ ...form, min: e.target.value })} className="border border-slate-300 rounded-lg px-3 py-2" />
                  <input placeholder="max" value={form.max} onChange={(e) => setForm({ ...form, max: e.target.value })} className="border border-slate-300 rounded-lg px-3 py-2" />
                </>}
                {form.rule_type === 'in_set' && <input placeholder="comma,separated,values" value={form.values} onChange={(e) => setForm({ ...form, values: e.target.value })} className="border border-slate-300 rounded-lg px-3 py-2 col-span-2" />}
              </div>
              <div className="flex gap-2 mb-4">
                <Button onClick={() => createRule.mutate()} disabled={!form.column || createRule.isPending}>Add rule</Button>
                <Button variant="ghost" onClick={() => autogen.mutate()} disabled={autogen.isPending}>Auto-generate rules</Button>
                <Button variant="ghost" onClick={() => run.mutate()} disabled={run.isPending}>Run checks</Button>
              </div>
              {runMsg && <div className="mb-4 text-sm bg-slate-100 rounded-lg px-4 py-2">{runMsg}</div>}

              <h4 className="font-medium text-sm mb-2">Rules ({rules?.length ?? 0})</h4>
              {rules?.length ? (
                <Table head={['Name', 'Dimension', 'Type', 'Config', 'Active']}>
                  {rules.map((r: any) => (
                    <tr key={r.id} className="border-b border-slate-100">
                      <td className="py-1 px-3">{r.name}</td>
                      <td className="py-1 px-3">{r.dimension}</td>
                      <td className="py-1 px-3">{r.rule_type}</td>
                      <td className="py-1 px-3 text-xs text-slate-500">{JSON.stringify(r.rule_config)}</td>
                      <td className="py-1 px-3">{r.is_active ? 'Yes' : 'No'}</td>
                    </tr>
                  ))}
                </Table>
              ) : <p className="text-sm text-slate-400 mb-4">No rules yet — add one above, then Run checks.</p>}

              {runs?.length ? (
                <div className="mt-4">
                  <h4 className="font-medium text-sm mb-2">Recent runs</h4>
                  <Table head={['Score', 'Passed', 'Failed', 'When']}>
                    {runs.map((r: any) => (
                      <tr key={r.id} className="border-b border-slate-100">
                        <td className="py-1 px-3">{r.overall_score != null ? `${r.overall_score.toFixed(0)}%` : '—'}</td>
                        <td className="py-1 px-3 text-green-600">{r.passed_rules}</td>
                        <td className="py-1 px-3 text-red-600">{r.failed_rules}</td>
                        <td className="py-1 px-3 text-slate-500">{r.run_at ? new Date(r.run_at).toLocaleString() : ''}</td>
                      </tr>
                    ))}
                  </Table>
                </div>
              ) : null}
            </>
          )}
        </Card>
      </div>
    </div>
  );
}
