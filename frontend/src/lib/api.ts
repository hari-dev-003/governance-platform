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
  publishOpenMetadata: async (id: string) => (await api.post(`/sources/${id}/publish-openmetadata`)).data,
};

export const assetsApi = {
  list: async (params?: any) => (await api.get('/assets', { params })).data,
  get: async (id: string) => (await api.get(`/assets/${id}`)).data,
  columns: async (id: string) => (await api.get(`/assets/${id}/columns`)).data,
  lineage: async (id: string) => (await api.get(`/assets/${id}/lineage`)).data,
  update: async (id: string, p: any) => (await api.patch(`/assets/${id}`, p)).data,
};

export const lineageApi = {
  graph: async () => (await api.get('/lineage/graph')).data,
  impact: async (id: string) => (await api.get(`/lineage/impact/${id}`)).data,
};

export const glossaryApi = {
  list: async () => (await api.get('/glossary')).data,
  create: async (p: any) => (await api.post('/glossary', p)).data,
  submit: async (id: string) => (await api.post(`/glossary/${id}/submit`)).data,
  approve: async (id: string) => (await api.post(`/glossary/${id}/approve`)).data,
};

export const classificationApi = {
  rules: async () => (await api.get('/classification/rules')).data,
  createRule: async (p: any) => (await api.post('/classification/rules', p)).data,
  run: async (sourceId: string) => (await api.post(`/classification/sources/${sourceId}/run`)).data,
  results: async () => (await api.get('/classification/results')).data,
};

export const qualityApi = {
  rules: async (assetId: string) => (await api.get('/quality/rules', { params: { asset_id: assetId } })).data,
  createRule: async (p: any) => (await api.post('/quality/rules', p)).data,
  run: async (assetId: string) => (await api.post(`/quality/assets/${assetId}/run`)).data,
  runs: async (assetId: string) => (await api.get('/quality/runs', { params: { asset_id: assetId } })).data,
};

export const privacyApi = {
  scan: async (sourceId: string) => (await api.post(`/privacy/sources/${sourceId}/scan`)).data,
  findings: async () => (await api.get('/privacy/findings')).data,
};

export const policiesApi = {
  list: async () => (await api.get('/policies')).data,
  create: async (p: any) => (await api.post('/policies', p)).data,
};

export const accessApi = {
  list: async () => (await api.get('/access-requests')).data,
  create: async (p: any) => (await api.post('/access-requests', p)).data,
  review: async (id: string, p: any) => (await api.post(`/access-requests/${id}/review`, p)).data,
};

export const modelsApi = {
  list: async () => (await api.get('/ai-models')).data,
  get: async (id: string) => (await api.get(`/ai-models/${id}`)).data,
  create: async (p: any) => (await api.post('/ai-models', p)).data,
  versions: async (id: string) => (await api.get(`/ai-models/${id}/versions`)).data,
  addVersion: async (id: string, p: any) => (await api.post(`/ai-models/${id}/versions`, p)).data,
  card: async (id: string) => (await api.get(`/ai-models/${id}/card`)).data,
};

export const riskApi = {
  questionnaire: async () => (await api.get('/risk-assessment/questionnaire')).data,
  submit: async (p: any) => (await api.post('/risk-assessment', p)).data,
};

export const biasApi = {
  list: async () => (await api.get('/bias-tests')).data,
  run: async (p: any) => (await api.post('/bias-tests', p)).data,
};

export const explainApi = {
  engines: async () => (await api.get('/explainability/engines')).data,
  explain: async (p: any) => (await api.post('/explainability/explain', p)).data,
  featureImportance: async (p: any) => (await api.post('/explainability/feature-importance', p)).data,
};

export const monitoringApi = {
  alerts: async () => (await api.get('/monitoring/alerts')).data,
  driftCheck: async (p: any) => (await api.post('/monitoring/drift-check', p)).data,
  evidentlyReport: async (p: any) => (await api.post('/monitoring/evidently-report', p)).data,
  acknowledge: async (id: string) => (await api.post(`/monitoring/alerts/${id}/acknowledge`)).data,
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
