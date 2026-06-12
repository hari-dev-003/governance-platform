import axios from 'axios';

const BASE = (import.meta.env.VITE_API_URL as string) || '/api/v1';
const TOKEN_KEY = 'dgp.token';

export const api = axios.create({ baseURL: BASE, headers: { 'Content-Type': 'application/json' } });

api.interceptors.request.use((cfg) => {
  const t = localStorage.getItem(TOKEN_KEY);
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  return cfg;
});
api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401 && !location.pathname.startsWith('/login')) {
      localStorage.removeItem(TOKEN_KEY);
      location.href = '/login';
    }
    return Promise.reject(err);
  },
);

export const tokenStore = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (t: string) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

export type Role = 'admin' | 'data_steward' | 'viewer' | 'ai_risk_officer';
export interface SessionUser { id?: string; email: string; full_name?: string | null; role: Role; org_id?: string | null; }

export const authApi = {
  async login(username: string, password: string) {
    const body = new URLSearchParams({ username, password });
    const r = await axios.post(`${BASE}/auth/login`, body, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
    return r.data as { access_token: string; role: Role; username: string; user_id: string; org_id: string };
  },
  me: async () => (await api.get('/auth/me')).data as SessionUser,
  users: async () => (await api.get('/auth/users')).data,
  createUser: async (p: any) => (await api.post('/auth/users', p)).data,
};

export const sourcesApi = {
  types: async () => (await api.get('/sources/types')).data as { connector_type: string; category: string }[],
  list: async () => (await api.get('/sources')).data,
  create: async (p: any) => (await api.post('/sources', p)).data,
  test: async (id: string) => (await api.post(`/sources/${id}/test`)).data,
  crawl: async (id: string) => (await api.post(`/sources/${id}/crawl`)).data,
  remove: async (id: string) => (await api.delete(`/sources/${id}`)).data,
};

export const assetsApi = {
  search: async (params?: any) => (await api.get('/assets', { params })).data,
  list: async (params?: any) => (await api.get('/assets', { params })).data,
  get: async (id: string) => (await api.get(`/assets/${id}`)).data,
  columns: async (id: string) => (await api.get(`/assets/${id}/columns`)).data,
  lineage: async (id: string) => (await api.get(`/assets/${id}/lineage`)).data,
  classifications: async (id: string) => (await api.get(`/assets/${id}/classifications`)).data,
  sample: async (id: string) => (await api.get(`/assets/${id}/sample`)).data,
  update: async (id: string, p: any) => (await api.patch(`/assets/${id}`, p)).data,
};

export const catalogApi = {
  overview: async () => (await api.get('/catalog/overview')).data,
  facets: async () => (await api.get('/catalog/facets')).data,
};

export const lineageApi = {
  graph: async (level: 'table' | 'column' = 'table') => (await api.get('/lineage/graph', { params: { level } })).data,
  rebuild: async () => (await api.post('/lineage/rebuild')).data,
  impact: async (id: string) => (await api.get(`/lineage/impact/${id}`)).data,
};

export const classificationApi = {
  rules: async () => (await api.get('/classification/rules')).data,
  createRule: async (p: any) => (await api.post('/classification/rules', p)).data,
  run: async (sourceId: string) => (await api.post(`/classification/sources/${sourceId}/run`)).data,
  results: async () => (await api.get('/classification/results')).data,
  runs: async () => (await api.get('/classification/runs')).data,
  runFindings: async (runId: string) => (await api.get(`/classification/runs/${runId}/findings`)).data,
};

export const qualityApi = {
  rules: async (assetId: string) => (await api.get('/quality/rules', { params: { asset_id: assetId } })).data,
  createRule: async (p: any) => (await api.post('/quality/rules', p)).data,
  run: async (assetId: string) => (await api.post(`/quality/assets/${assetId}/run`)).data,
  autogenerate: async (assetId: string) => (await api.post(`/quality/assets/${assetId}/autogenerate`)).data,
  runs: async (assetId: string) => (await api.get('/quality/runs', { params: { asset_id: assetId } })).data,
};

export const privacyApi = {
  scan: async (sourceId: string) => (await api.post(`/privacy/sources/${sourceId}/scan`)).data,
  findings: async () => (await api.get('/privacy/findings')).data,
};

export const accessApi = {
  list: async () => (await api.get('/access-requests')).data,
  create: async (p: any) => (await api.post('/access-requests', p)).data,
  review: async (id: string, p: any) => (await api.post(`/access-requests/${id}/review`, p)).data,
};

// Download a binary (PDF) response and save it via a temporary object URL.
async function download(url: string, filename: string) {
  const res = await api.get(url, { responseType: 'blob' });
  const href = URL.createObjectURL(res.data as Blob);
  const a = document.createElement('a');
  a.href = href; a.download = filename;
  document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(href);
}

export const modelsApi = {
  list: async () => (await api.get('/ai-models')).data,
  get: async (id: string) => (await api.get(`/ai-models/${id}`)).data,
  create: async (p: any) => (await api.post('/ai-models', p)).data,
  sync: async (sourceId: string) => (await api.post(`/ai-models/sync/${sourceId}`)).data,
  versions: async (id: string) => (await api.get(`/ai-models/${id}/versions`)).data,
  addVersion: async (id: string, p: any) => (await api.post(`/ai-models/${id}/versions`, p)).data,
  validateVersion: async (id: string, vid: string, p: any) =>
    (await api.post(`/ai-models/${id}/versions/${vid}/validate`, p)).data,
  lineage: async (id: string) => (await api.get(`/ai-models/${id}/lineage`)).data,
  card: async (id: string) => (await api.get(`/ai-models/${id}/card`)).data,
  downloadCard: async (id: string) => download(`/ai-models/${id}/card.pdf`, `model-card-${id}.pdf`),
};

export const riskApi = {
  questionnaire: async () => (await api.get('/risk-assessment/questionnaire')).data,
  submit: async (p: any) => (await api.post('/risk-assessment', p)).data,
  approve: async (id: string) => (await api.post(`/risk-assessment/${id}/approve`)).data,
  downloadReport: async (id: string) => download(`/risk-assessment/${id}/report`, `risk-assessment-${id}.pdf`),
};

export const biasApi = {
  list: async () => (await api.get('/bias-tests')).data,
  run: async (p: any) => (await api.post('/bias-tests', p)).data,
  downloadReport: async (id: string) => download(`/bias-tests/${id}/report`, `bias-report-${id}.pdf`),
};

export const explainApi = {
  explain: async (p: any) => (await api.post('/explainability/explain', p)).data,
  featureImportance: async (vid: string) => (await api.get(`/explainability/feature-importance/${vid}`)).data,
  computeFeatureImportance: async (vid: string, p: any) =>
    (await api.post(`/explainability/versions/${vid}/feature-importance`, p)).data,
};

export const monitoringApi = {
  alerts: async () => (await api.get('/monitoring/alerts')).data,
  driftCheck: async (p: any) => (await api.post('/monitoring/drift-check', p)).data,
  evidentlyReport: async (p: any) => (await api.post('/monitoring/evidently-report', p)).data,
  acknowledge: async (id: string) => (await api.post(`/monitoring/alerts/${id}/acknowledge`)).data,
  configs: async (versionId?: string) =>
    (await api.get('/monitoring/configs', { params: versionId ? { model_version_id: versionId } : {} })).data,
  createConfig: async (p: any) => (await api.post('/monitoring/configs', p)).data,
  updateConfig: async (id: string, p: any) => (await api.patch(`/monitoring/configs/${id}`, p)).data,
  deleteConfig: async (id: string) => (await api.delete(`/monitoring/configs/${id}`)).data,
  runAll: async () => (await api.post('/monitoring/run-all')).data,
};

export const complianceApi = {
  frameworks: async () => (await api.get('/compliance/frameworks')).data,
  mappings: async () => (await api.get('/compliance/mappings')).data,
  createMapping: async (p: any) => (await api.post('/compliance/mappings', p)).data,
  summary: async () => (await api.get('/compliance/summary')).data,
};

export const auditApi = {
  logs: async (params?: any) => (await api.get('/audit/logs', { params })).data,
};

export const dashboardApi = {
  get: async () => (await api.get('/dashboard')).data,
};
