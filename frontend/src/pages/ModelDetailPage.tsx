import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { modelsApi, riskApi, biasApi, explainApi } from '../lib/api';
import { PageHeader, Card, Button, Badge, Table, Empty } from '../components/ui';
import { EChart } from '../components/EChart';

export default function ModelDetailPage() {
  const { id = '' } = useParams();
  const qc = useQueryClient();
  const [tab, setTab] = useState<'overview' | 'risk' | 'bias' | 'explain'>('overview');
  const { data: model } = useQuery({ queryKey: ['model', id], queryFn: () => modelsApi.get(id) });
  const { data: versions } = useQuery({ queryKey: ['versions', id], queryFn: () => modelsApi.versions(id) });
  const { data: quiz } = useQuery({ queryKey: ['quiz'], queryFn: riskApi.questionnaire });

  const { data: mlineage } = useQuery({ queryKey: ['mlineage', id], queryFn: () => modelsApi.lineage(id) });

  const [responses, setResponses] = useState<Record<string, boolean>>({});
  const [riskResult, setRiskResult] = useState<any>(null);
  const submitRisk = useMutation({ mutationFn: () => riskApi.submit({ model_id: id, responses }),
    onSuccess: (r) => { setRiskResult(r); qc.invalidateQueries({ queryKey: ['model', id] }); } });

  // version validation / promotion
  const validateVersion = useMutation({
    mutationFn: ({ vid, decision, stage }: { vid: string; decision: string; stage?: string }) =>
      modelsApi.validateVersion(id, vid, { decision, stage }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['versions', id] }),
  });

  const [biasResult, setBiasResult] = useState<any>(null);
  const runBias = useMutation({
    mutationFn: () => biasApi.run({
      model_version_id: versions?.[0]?.id, protected_attribute: 'gender',
      records: [
        { gender: 'M', label: '1', prediction: '1' }, { gender: 'M', label: '0', prediction: '1' },
        { gender: 'M', label: '1', prediction: '1' }, { gender: 'F', label: '1', prediction: '0' },
        { gender: 'F', label: '0', prediction: '0' }, { gender: 'F', label: '1', prediction: '0' },
      ],
    }),
    onSuccess: (r) => setBiasResult(r),
  });

  const [explain, setExplain] = useState<any>(null);
  // small labelled demo dataset (numeric features + binary label) -> SHAP + LIME
  const demoRecords = Array.from({ length: 60 }, (_, i) => {
    const income = 30 + (i * 7) % 90, age = 20 + (i * 3) % 50,
      credit_history = (i * 5) % 100, debt = (i * 11) % 60;
    const label = income - debt + credit_history / 2 > 70 ? 1 : 0;
    return { income, age, credit_history, debt, label };
  });
  const runExplain = useMutation({
    mutationFn: () => explainApi.explain({ records: demoRecords, label_col: 'label', instance_index: 0 }),
    onSuccess: (r) => setExplain(r),
  });

  if (!model) return <Empty message="Loading…" />;
  const TABS = [['overview', 'Overview'], ['risk', 'Risk Assessment'], ['bias', 'Bias & Fairness'], ['explain', 'Explainability']] as const;

  return (
    <div>
      <PageHeader title={model.name} subtitle={`${model.model_type} · ${model.framework ?? ''} · ${model.business_domain ?? ''}`}
        actions={
          <div className="flex gap-2">
            <Button variant="ghost" onClick={() => modelsApi.downloadCard(id)}>Download model card (PDF)</Button>
            <Link to="/ai-models"><Button variant="ghost">← Registry</Button></Link>
          </div>
        } />
      <div className="flex gap-2 mb-6">
        {TABS.map(([k, label]) => (
          <button key={k} onClick={() => setTab(k as any)}
            className={`px-4 py-2 rounded-lg text-sm font-medium ${tab === k ? 'bg-brand-600 text-white' : 'bg-white border border-slate-300 text-slate-600'}`}>{label}</button>
        ))}
      </div>

      {tab === 'overview' && (
        <div className="grid md:grid-cols-3 gap-6">
          <Card className="p-5 md:col-span-2">
            <h3 className="font-semibold mb-3">Versions</h3>
            {versions?.length ? (
              <Table head={['Version', 'Stage', 'Accuracy', 'Validation', 'Actions']}>
                {versions.map((v: any) => (
                  <tr key={v.id} className="border-b border-slate-100">
                    <td className="py-2 px-3">{v.version_number}</td>
                    <td className="py-2 px-3"><Badge>{v.stage}</Badge></td>
                    <td className="py-2 px-3">{v.metrics?.accuracy ?? '—'}</td>
                    <td className="py-2 px-3"><Badge>{v.validation_status}</Badge></td>
                    <td className="py-2 px-3">
                      <div className="flex gap-1 flex-wrap">
                        <Button variant="ghost" onClick={() => validateVersion.mutate({ vid: v.id, decision: 'approved', stage: 'production' })}>Approve→Prod</Button>
                        <Button variant="ghost" onClick={() => validateVersion.mutate({ vid: v.id, decision: 'rejected' })}>Reject</Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </Table>
            ) : <Empty message="No versions. Add one via the API or registry sync." />}

            {mlineage?.versions?.some((v: any) => v.training_datasets?.length) && (
              <div className="mt-5">
                <h4 className="font-medium text-sm mb-2">Training-data lineage</h4>
                <ul className="text-sm space-y-1">
                  {mlineage.versions.map((v: any) => v.training_datasets?.length ? (
                    <li key={v.id} className="text-slate-600">
                      <span className="font-medium">v{v.version_number}</span>
                      {' ← '}{v.training_datasets.map((d: any) => d.name).join(', ')}
                    </li>
                  ) : null)}
                </ul>
              </div>
            )}
          </Card>
          <Card className="p-5">
            <h3 className="font-semibold mb-3">Governance</h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between"><span className="text-slate-500">Risk tier</span><Badge>{model.risk_tier}</Badge></div>
              <div className="flex justify-between"><span className="text-slate-500">Assessment</span><Badge>{model.risk_assessment_status}</Badge></div>
              <div className="flex justify-between"><span className="text-slate-500">Deployment</span><Badge>{model.deployment_status}</Badge></div>
            </div>
            <p className="text-sm text-slate-500 mt-3">{model.use_case}</p>
          </Card>
        </div>
      )}

      {tab === 'risk' && (
        <Card className="p-5">
          <h3 className="font-semibold mb-3">EU AI Act Risk Questionnaire</h3>
          <div className="space-y-2 mb-4">
            {quiz?.questions?.map((q: any) => (
              <label key={q.key} className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={!!responses[q.key]} onChange={(e) => setResponses({ ...responses, [q.key]: e.target.checked })} />
                {q.text}
              </label>
            ))}
          </div>
          <Button onClick={() => submitRisk.mutate()}>Assess Risk</Button>
          {riskResult && (
            <div className="mt-4 p-4 bg-slate-50 rounded-lg">
              <div className="flex items-center gap-2 mb-2"><span className="font-semibold">Result:</span><Badge>{riskResult.risk_tier}</Badge><span className="text-sm text-slate-500">{riskResult.eu_ai_act_category}</span></div>
              <div className="text-sm font-medium mt-2">Required actions:</div>
              <ul className="list-disc ml-5 text-sm text-slate-600">{riskResult.required_actions?.map((a: string, i: number) => <li key={i}>{a}</li>)}</ul>
            </div>
          )}
        </Card>
      )}

      {tab === 'bias' && (
        <Card className="p-5">
          <h3 className="font-semibold mb-3">Bias & Fairness Test (demo dataset, protected attr = gender)</h3>
          <Button onClick={() => runBias.mutate()} disabled={!versions?.length}>Run Bias Test</Button>
          {!versions?.length && <p className="text-sm text-amber-600 mt-2">Add a model version first.</p>}
          {biasResult && (
            <div className="mt-4">
              <div className="flex items-center gap-2 mb-3"><span className="font-semibold">Verdict:</span><Badge>{biasResult.verdict}</Badge>
                <span className="text-xs text-slate-500">engine: {biasResult.engine}</span>
                {biasResult.id && <Button variant="ghost" onClick={() => biasApi.downloadReport(biasResult.id)}>Download report (PDF)</Button>}</div>
              <EChart height={280} option={{
                tooltip: {}, legend: { bottom: 0 }, xAxis: { type: 'category', data: biasResult.groups },
                yAxis: { type: 'value', max: 1 },
                series: [
                  { name: 'Demographic Parity', type: 'bar', data: biasResult.groups.map((g: string) => biasResult.demographic_parity[g]) },
                  { name: 'Equal Opportunity', type: 'bar', data: biasResult.groups.map((g: string) => biasResult.equal_opportunity[g]) },
                ],
              }} />
            </div>
          )}
        </Card>
      )}

      {tab === 'explain' && (
        <Card className="p-5">
          <h3 className="font-semibold mb-1">Explainability - SHAP (global) + LIME (local)</h3>
          <p className="text-xs text-slate-500 mb-3">Fits a surrogate model on a demo dataset, then computes SHAP importances and a LIME explanation for one instance.</p>
          <Button onClick={() => runExplain.mutate()} disabled={runExplain.isPending}>{runExplain.isPending ? 'Computing...' : 'Compute SHAP + LIME'}</Button>
          {explain && (
            <div className="mt-4">
              <div className="text-xs text-slate-500 mb-2">engine: {explain.engine}</div>
              {explain.global_importance?.length ? (<>
                <div className="font-medium text-sm mb-1">SHAP - Global Feature Importance</div>
                <EChart height={240} option={{
                  tooltip: {}, grid: { left: 130 },
                  xAxis: { type: 'value' },
                  yAxis: { type: 'category', data: explain.global_importance.map((f: any) => f.feature).reverse() },
                  series: [{ type: 'bar', data: explain.global_importance.map((f: any) => f.importance).reverse(), itemStyle: { color: '#8b5cf6' } }],
                }} />
              </>) : null}
              {explain.local_explanation?.length ? (<div className="mt-4">
                <div className="font-medium text-sm mb-2">LIME - Local Explanation (instance 0)</div>
                <ul className="text-sm space-y-1">
                  {explain.local_explanation.map((l: any, i: number) => (
                    <li key={i} className="flex justify-between border-b border-slate-100 py-1">
                      <span>{l.feature}</span>
                      <span className={l.weight >= 0 ? 'text-green-600' : 'text-red-600'}>{l.weight >= 0 ? '+' : ''}{l.weight}</span>
                    </li>
                  ))}
                </ul>
              </div>) : null}
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
