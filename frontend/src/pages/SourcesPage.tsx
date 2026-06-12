import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { sourcesApi } from '../lib/api';
import { PageHeader, Card, Button, Badge, Table, Empty } from '../components/ui';

const CONFIG_HINTS: Record<string, string[]> = {
  postgresql: ['host', 'port', 'database', 'username', 'password'],
  mssql: ['host', 'port', 'database', 'username', 'password'],
  mysql: ['host', 'port', 'database', 'username', 'password'],
  aws_s3: ['aws_access_key_id', 'aws_secret_access_key', 'region'],
  redshift: ['host', 'port', 'database', 'username', 'password'],
  mlflow: ['tracking_uri'],
  sagemaker: ['aws_access_key_id', 'aws_secret_access_key', 'region'],
  vertex_ai: ['service_account_json', 'project_id', 'location'],
  azure_ml: ['tenant_id', 'client_id', 'client_secret', 'subscription_id', 'resource_group', 'workspace_name'],
  github_etl: ['github_token', 'repo_name', 'branch', 'path'],
  etl_repo: ['repo_kind', 'local_path', 'git_url', 'branch', 'subpath', 'auth_token'],
  keycloak: ['server_url', 'realm', 'admin_username', 'admin_password'],
};

// One-line guidance shown under the form for each connector type.
const CONNECTOR_HELP: Record<string, string> = {
  mlflow: 'Tracking URI of your MLflow server, e.g. http://mlflow.mycorp.com:5000',
  sagemaker: 'IAM access key with sagemaker:List/Describe permissions. Region e.g. us-east-1.',
  vertex_ai: 'Paste the full service-account JSON key. project_id is your GCP project; location e.g. us-central1.',
  azure_ml: 'Service-principal credentials (App registration) with Reader on the Azure ML workspace.',
};

// Fields rendered as a multi-line textarea (large pasted blobs like JSON keys).
const TEXTAREA_FIELDS = new Set(['service_account_json']);
const isSecret = (f: string) => /password|secret|token/.test(f);
const prettyField = (f: string) => f.replace(/_/g, ' ');

export default function SourcesPage() {
  const qc = useQueryClient();
  const [showWizard, setShowWizard] = useState(false);
  const { data: sources } = useQuery({ queryKey: ['sources'], queryFn: sourcesApi.list });
  const { data: types } = useQuery({ queryKey: ['types'], queryFn: sourcesApi.types });

  const [name, setName] = useState('');
  const [ctype, setCtype] = useState('postgresql');
  const [cfg, setCfg] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState('');
  const [confirmId, setConfirmId] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () => sourcesApi.create({ name, connector_type: ctype, config: coerce(cfg) }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['sources'] }); setShowWizard(false); setName(''); setCfg({}); },
  });
  const test = useMutation({ mutationFn: (id: string) => sourcesApi.test(id),
    onSuccess: (r: any) => setMsg(r.success ? `✓ ${r.message}` : `✗ ${r.message}`) });
  const crawl = useMutation({ mutationFn: (id: string) => sourcesApi.crawl(id),
    onSuccess: (r: any) => setMsg(r.message) });
  const remove = useMutation({
    mutationFn: (id: string) => sourcesApi.remove(id),
    onSuccess: () => {
      // A source delete cascades across catalog, lineage, classification, etc.,
      // so refresh everything rather than a single query.
      qc.invalidateQueries();
      setConfirmId(null);
      setMsg('Source deleted, along with all its assets, lineage and results.');
    },
    onError: (e: any) => {
      setConfirmId(null);
      setMsg('Delete failed: ' + (e?.response?.data?.detail ?? e?.message ?? 'unknown error'));
    },
  });
  const confirmSource = sources?.find((s: any) => s.id === confirmId);

  function coerce(c: Record<string, string>) {
    const out: any = { ...c };
    if (out.port) out.port = Number(out.port);
    return out;
  }
  const fields = CONFIG_HINTS[ctype] ?? ['host', 'port', 'database', 'username', 'password'];

  return (
    <div>
      <PageHeader title="Data Sources" subtitle="Connect databases, lakes, warehouses, ETL, model registries & IAM"
        actions={<Button onClick={() => setShowWizard((s) => !s)}>{showWizard ? 'Cancel' : '+ Add Source'}</Button>} />
      {msg && <div className="mb-4 text-sm bg-slate-100 rounded-lg px-4 py-2">{msg}</div>}

      {showWizard && (
        <Card className="p-5 mb-6">
          <h3 className="font-semibold mb-3">New Connection</h3>
          <div className="grid md:grid-cols-2 gap-3 mb-3">
            <input placeholder="Connection name" value={name} onChange={(e) => setName(e.target.value)}
              className="border border-slate-300 rounded-lg px-3 py-2" />
            <select value={ctype} onChange={(e) => { setCtype(e.target.value); setCfg({}); }}
              className="border border-slate-300 rounded-lg px-3 py-2">
              {types?.map((t) => <option key={t.connector_type} value={t.connector_type}>{t.connector_type} ({t.category})</option>)}
            </select>
          </div>
          <div className="grid md:grid-cols-2 gap-3 mb-3">
            {fields.map((f) => (
              TEXTAREA_FIELDS.has(f) ? (
                <textarea key={f} placeholder={prettyField(f)} rows={5}
                  value={cfg[f] ?? ''} onChange={(e) => setCfg({ ...cfg, [f]: e.target.value })}
                  className="border border-slate-300 rounded-lg px-3 py-2 md:col-span-2 font-mono text-xs" />
              ) : (
                <input key={f} placeholder={prettyField(f)} type={isSecret(f) ? 'password' : 'text'}
                  value={cfg[f] ?? ''} onChange={(e) => setCfg({ ...cfg, [f]: e.target.value })}
                  className="border border-slate-300 rounded-lg px-3 py-2" />
              )
            ))}
          </div>
          {CONNECTOR_HELP[ctype] && <p className="text-xs text-slate-500 mb-3">{CONNECTOR_HELP[ctype]}</p>}
          <Button onClick={() => create.mutate()} disabled={!name || create.isPending}>
            {create.isPending ? 'Saving…' : 'Save Connection'}
          </Button>
        </Card>
      )}

      <Card className="p-5">
        {sources?.length ? (
          <Table head={['Name', 'Type', 'Category', 'Status', 'Last Crawled', 'Actions']}>
            {sources.map((s: any) => (
              <tr key={s.id} className="border-b border-slate-100">
                <td className="py-2 px-3 font-medium">{s.name}</td>
                <td className="py-2 px-3">{s.connector_type}</td>
                <td className="py-2 px-3">{s.category}</td>
                <td className="py-2 px-3"><Badge>{s.status}</Badge></td>
                <td className="py-2 px-3 text-slate-500">{s.last_crawled_at ? new Date(s.last_crawled_at).toLocaleString() : '—'}</td>
                <td className="py-2 px-3 flex gap-2">
                  <Button variant="ghost" onClick={() => test.mutate(s.id)}>Test</Button>
                  <Button variant="ghost" onClick={() => crawl.mutate(s.id)}>Scan</Button>
                  <Button variant="danger" onClick={() => setConfirmId(s.id)}>Delete</Button>
                </td>
              </tr>
            ))}
          </Table>
        ) : <Empty message="No sources yet. Add your first connection." />}
      </Card>

      {confirmSource && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 px-4"
          onClick={() => !remove.isPending && setConfirmId(null)}>
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-semibold text-slate-900">Delete “{confirmSource.name}”?</h3>
            <p className="text-sm text-slate-500 mt-2">
              This permanently removes the source and everything derived from it — all
              catalogued assets, lineage edges, classification results, quality checks and
              any registered models. This cannot be undone.
            </p>
            <div className="flex justify-end gap-2 mt-5">
              <Button variant="ghost" onClick={() => setConfirmId(null)} disabled={remove.isPending}>Cancel</Button>
              <Button variant="danger" onClick={() => remove.mutate(confirmSource.id)} disabled={remove.isPending}>
                {remove.isPending ? 'Deleting…' : 'Delete source'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
