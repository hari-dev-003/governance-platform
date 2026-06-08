import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { assetsApi } from '../lib/api';
import { PageHeader, Card, Badge, Table, Empty } from '../components/ui';

export default function CatalogPage() {
  const [q, setQ] = useState('');
  const [type, setType] = useState('');
  const [sensitivity, setSensitivity] = useState('');
  const { data, isLoading } = useQuery({
    queryKey: ['assets', q, type, sensitivity],
    queryFn: () => assetsApi.list({ q: q || undefined, type: type || undefined, sensitivity: sensitivity || undefined }),
  });

  return (
    <div>
      <PageHeader title="Data Catalog" subtitle="Search and govern every discovered asset" />
      <Card className="p-4 mb-4 flex flex-wrap gap-3">
        <input placeholder="Search name or path…" value={q} onChange={(e) => setQ(e.target.value)}
          className="border border-slate-300 rounded-lg px-3 py-2 flex-1 min-w-[200px]" />
        <select value={type} onChange={(e) => setType(e.target.value)} className="border border-slate-300 rounded-lg px-3 py-2">
          <option value="">All types</option>
          {['schema', 'table', 'column', 'file', 'bucket', 'ml_model', 'etl_pipeline'].map((t) => <option key={t}>{t}</option>)}
        </select>
        <select value={sensitivity} onChange={(e) => setSensitivity(e.target.value)} className="border border-slate-300 rounded-lg px-3 py-2">
          <option value="">All sensitivity</option>
          {['unclassified', 'public', 'internal', 'confidential', 'restricted'].map((t) => <option key={t}>{t}</option>)}
        </select>
      </Card>
      <Card className="p-5">
        {isLoading ? <Empty message="Loading…" /> : data?.length ? (
          <Table head={['Name', 'Type', 'Sensitivity', 'Quality', 'Domain']}>
            {data.map((a: any) => (
              <tr key={a.id} className="border-b border-slate-100 hover:bg-slate-50">
                <td className="py-2 px-3"><Link to={`/catalog/${a.id}`} className="text-brand-600 font-medium hover:underline">{a.name}</Link></td>
                <td className="py-2 px-3">{a.asset_type}</td>
                <td className="py-2 px-3"><Badge>{a.sensitivity_level}</Badge></td>
                <td className="py-2 px-3">{a.quality_score != null ? `${a.quality_score.toFixed(0)}%` : '—'}</td>
                <td className="py-2 px-3 text-slate-500">{a.domain ?? '—'}</td>
              </tr>
            ))}
          </Table>
        ) : <Empty message="No assets found. Add a source and run a scan." />}
      </Card>
    </div>
  );
}
