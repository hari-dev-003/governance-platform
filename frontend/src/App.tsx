import { BrowserRouter, Routes, Route } from 'react-router-dom';
import ProtectedRoute from './components/ProtectedRoute';
import Layout from './components/Layout';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import SourcesPage from './pages/SourcesPage';
import CatalogPage from './pages/CatalogPage';
import AssetDetailPage from './pages/AssetDetailPage';
import LineagePage from './pages/LineagePage';
import GlossaryPage from './pages/GlossaryPage';
import ClassificationPage from './pages/ClassificationPage';
import QualityPage from './pages/QualityPage';
import PoliciesPage from './pages/PoliciesPage';
import AccessPage from './pages/AccessPage';
import ModelRegistryPage from './pages/ModelRegistryPage';
import ModelDetailPage from './pages/ModelDetailPage';
import MonitoringPage from './pages/MonitoringPage';
import CompliancePage from './pages/CompliancePage';
import AuditPage from './pages/AuditPage';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/*" element={
          <ProtectedRoute>
            <Layout>
              <Routes>
                <Route path="/" element={<DashboardPage />} />
                <Route path="/sources" element={<SourcesPage />} />
                <Route path="/catalog" element={<CatalogPage />} />
                <Route path="/catalog/:id" element={<AssetDetailPage />} />
                <Route path="/lineage" element={<LineagePage />} />
                <Route path="/glossary" element={<GlossaryPage />} />
                <Route path="/classification" element={<ClassificationPage />} />
                <Route path="/quality" element={<QualityPage />} />
                <Route path="/policies" element={<PoliciesPage />} />
                <Route path="/access" element={<AccessPage />} />
                <Route path="/ai-models" element={<ModelRegistryPage />} />
                <Route path="/ai-models/:id" element={<ModelDetailPage />} />
                <Route path="/monitoring" element={<MonitoringPage />} />
                <Route path="/compliance" element={<CompliancePage />} />
                <Route path="/audit" element={<AuditPage />} />
              </Routes>
            </Layout>
          </ProtectedRoute>
        } />
      </Routes>
    </BrowserRouter>
  );
}
