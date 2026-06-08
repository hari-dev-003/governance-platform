import { useQuery } from '@tanstack/react-query';
import { dashboardApi } from '../lib/api';
import { PageHeader, Card, Stat, Badge, Empty } from '../components/ui';
import { EChart } from '../components/EChart';

export default function DashboardPage() {
  const { data, isLoading } = useQuery({ queryKey: ['dashboard'], queryFn: dashboardApi.get });
  if (isLoading || !data) return <Empty message="Loading dashboard…" />;

  const sens = data.sensitivity_mix || {};
  const risk = data.risk_tier_mix || {};
  const pie = (obj: any, name: string) => ({
    tooltip: { trigger: 'item' },
    legend: { bottom: 0 },
    series: [{ name, type: 'pie', radius: ['40%', '70%'], data: Object.entries(obj).map(([k, v]) => ({ name: k, value: v })) }],
  });

  return (
    <div>
      <PageHeader title="Governance Dashboard" subtitle="Unified view across data and AI governance" />
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
        <Stat label="Data Assets" value={data.total_assets} />
        <Stat label="Sources" value={data.data_sources} />
        <Stat label="Lineage Edges" value={data.lineage_edges} />
        <Stat label="AI Models" value={data.ai_models} accent="text-purple-600" />
        <Stat label="Open Drift Alerts" value={data.open_drift_alerts} accent="text-red-600" />
      </div>
      <div className="grid md:grid-cols-2 gap-6 mb-6">
        <Card className="p-5"><h3 className="font-semibold mb-2">Data Sensitivity Mix</h3>
          {Object.keys(sens).length ? <EChart option={pie(sens, 'Sensitivity')} /> : <Empty message="No classified assets yet" />}</Card>
        <Card className="p-5"><h3 className="font-semibold mb-2">AI Risk Tiers</h3>
          {Object.keys(risk).length ? <EChart option={pie(risk, 'Risk Tier')} /> : <Empty message="No assessed models yet" />}</Card>
      </div>
      <Card className="p-5">
        <h3 className="font-semibold mb-3">Recent Activity</h3>
        {data.recent_activity?.length ? (
          <ul className="space-y-2">
            {data.recent_activity.map((a: any, i: number) => (
              <li key={i} className="flex items-center justify-between text-sm border-b border-slate-100 pb-2">
                <span><Badge>{a.action?.split('.')[0]}</Badge> <span className="ml-2 text-slate-600">{a.action} {a.resource_name ? `· ${a.resource_name}` : ''}</span></span>
                <span className="text-slate-400 text-xs">{a.occurred_at ? new Date(a.occurred_at).toLocaleString() : ''}</span>
              </li>
            ))}
          </ul>
        ) : <Empty message="No activity yet" />}
      </Card>
    </div>
  );
}
