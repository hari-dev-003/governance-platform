import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { assetsApi, qualityApi } from '../lib/api';
import { PageHeader, Card, Button, Table, Empty } from '../components/ui';

export default function QualityPage() {
  const qc = useQueryClient();
  const { data: tables } = useQuery({ queryKey: ['qtables'], queryFn: () => assetsApi.list({ type: 'table', limit: 200 }) });
  const run = useMutation({ mutationFn: (id: string) => qualityApi.run(id), onSuccess: () => qc.invalidateQueries({ queryKey: ['qtables'] }) });

  const scored = (tables ?? []).filter((t: any) => t.quality_score != null);
  const avg = scored.length ? scored.reduce((s: number, t: any) => s + t.quality_score, 0) / scored.length : null;

  return (
    <div>
      <PageHeader title="Data Quality" subtitle="Completeness · uniqueness · validity · freshness" />
      <div className="grid grid-cols-3 gap-4 mb-6">
        <Card className="p-5"><div className="text-xs uppercase text-slate-500">Tables</div><div className="text-3xl font-bold">{tables?.length ?? 0}</div></Card>
        <Card className="p-5"><div className="text-xs uppercase text-slate-500">Scored</div><div className="text-3xl font-bold">{scored.length}</div></Card>
        <Card className="p-5"><div className="text-xs uppercase text-slate-500">Avg Score</div><div className="text-3xl font-bold">{avg != null ? `${avg.toFixed(0)}%` : '—'}</div></Card>
      </div>
      <Card className="p-5">
        {tables?.length ? (
          <Table head={['Table', 'Quality Score', 'Action']}>
            {tables.map((t: any) => (
              <tr key={t.id} className="border-b border-slate-100">
                <td className="py-2 px-3"><Link to={`/catalog/${t.id}`} className="text-brand-600 hover:underline">{t.name}</Link></td>
                <td className="py-2 px-3">{t.quality_score != null ? `${t.quality_score.toFixed(0)}%` : '—'}</td>
                <td className="py-2 px-3"><Button variant="ghost" onClick={() => run.mutate(t.id)}>Run checks</Button></td>
              </tr>
            ))}
          </Table>
        ) : <Empty message="No tables. Add a database source and scan it." />}
      </Card>
    </div>
  );
}
