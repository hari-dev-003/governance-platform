import { useQuery } from '@tanstack/react-query';
import { complianceApi } from '../lib/api';
import { PageHeader, Card, Badge, Empty } from '../components/ui';

export default function CompliancePage() {
  const { data: frameworks } = useQuery({ queryKey: ['frameworks'], queryFn: complianceApi.frameworks });
  return (
    <div>
      <PageHeader title="Compliance Center" subtitle="GDPR · DPDPA · EU AI Act · PCI-DSS requirement tracking" />
      <div className="space-y-6">
        {frameworks?.length ? frameworks.map((fw: any) => (
          <Card key={fw.id} className="p-5">
            <div className="flex items-center gap-2 mb-1">
              <h3 className="font-semibold text-lg">{fw.name}</h3>
              <span className="text-xs text-slate-400">v{fw.version}</span>
            </div>
            <p className="text-sm text-slate-500 mb-3">{fw.description}</p>
            <div className="space-y-2">
              {fw.requirements?.map((r: any) => (
                <div key={r.id} className="flex items-start justify-between border-b border-slate-100 py-2">
                  <div>
                    <span className="font-medium text-sm">{r.article_reference}</span>
                    <span className="ml-2 text-sm">{r.title}</span>
                    <p className="text-xs text-slate-500">{r.description}</p>
                  </div>
                  {r.applies_to_risk_tiers?.length ? <div className="flex gap-1">{r.applies_to_risk_tiers.map((t: string) => <Badge key={t}>{t}</Badge>)}</div> : null}
                </div>
              ))}
            </div>
          </Card>
        )) : <Empty message="Loading frameworks…" />}
      </div>
    </div>
  );
}
