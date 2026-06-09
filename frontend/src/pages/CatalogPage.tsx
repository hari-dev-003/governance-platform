import { useState, useMemo } from 'react';
import { useQuery, keepPreviousData } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Database, Table2, Columns3, Plug, ShieldAlert, Gauge, Rows3, Search } from 'lucide-react';
import { assetsApi, catalogApi } from '../lib/api';
import { PageHeader, Card, Badge, Empty } from '../components/ui';
import { EChart } from '../components/EChart';

const TYPE_ICON: Record<string, any> = { table: Table2, column: Columns3, schema: Database, ml_model: ShieldAlert, etl_pipeline: Plug };
const LIMIT = 20;

function StatCard({ icon: Icon, label, value, accent = 'text-slate-900' }: any) {
  return (
    <Card className="p-4 flex items-center gap-3">
      <div className="w-10 h-10 rounded-lg bg-brand-50 grid place-items-center text-brand-600"><Icon size={20} /></div>
      <div><div className="text-[11px] uppercase tracking-wide text-slate-500">{label}</div>
        <div className={`text-xl font-bold ${accent}`}>{value}</div></div>
    </Card>
  );
}

export default function CatalogPage() {
  const { data: ov } = useQuery({ queryKey: ['catalog-overview'], queryFn: catalogApi.overview });
  const { data: facets } = useQuery({ queryKey: ['catalog-facets'], queryFn: catalogApi.facets });

  const [q, setQ] = useState('');
  const [type, setType] = useState('');
  const [sensitivity, setSensitivity] = useState('');
  const [sourceId, setSourceId] = useState('');
  const [sort, setSort] = useState('recent');
  const [offset, setOffset] = useState(0);

  const params = { q: q || undefined, type: type || undefined, sensitivity: sensitivity || undefined,
    source_id: sourceId || undefined, sort, limit: LIMIT, offset };
  const { data: res } = useQuery({ queryKey: ['assets', params], queryFn: () => assetsApi.search(params), placeholderData: keepPreviousData });

  const sourceName = useMemo(() => {
    const m: Record<string, string> = {};
    (facets?.sources ?? []).forEach((s: any) => { m[s.id] = s.name; });
    return m;
  }, [facets]);

  const items = res?.items ?? [];
  const total = res?.total ?? 0;
  const reset = (fn: () => void) => { fn(); setOffset(0); };

  const pie = (obj: any) => ({ tooltip: { trigger: 'item' }, legend: { bottom: 0, type: 'scroll' },
    series: [{ type: 'pie', radius: ['45%', '70%'], data: Object.entries(obj || {}).map(([k, v]) => ({ name: k, value: v })) }] });
  const bar = (rows: any[], nameKey: string, color: string) => ({ tooltip: {}, grid: { left: 90, top: 10, bottom: 20, right: 10 },
    xAxis: { type: 'value' }, yAxis: { type: 'category', data: (rows || []).map((r) => r[nameKey]).reverse() },
    series: [{ type: 'bar', data: (rows || []).map((r) => r.count).reverse(), itemStyle: { color } }] });

  return (
    <div>
      <PageHeader title="Data Catalog" subtitle="Discover, search and govern every data asset" />

      {/* overview */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3 mb-5">
        <StatCard icon={Database} label="Assets" value={ov?.total_assets ?? '—'} />
        <StatCard icon={Plug} label="Sources" value={ov?.counts?.sources ?? '—'} />
        <StatCard icon={Table2} label="Tables" value={ov?.counts?.tables ?? '—'} />
        <StatCard icon={Columns3} label="Columns" value={ov?.counts?.columns ?? '—'} />
        <StatCard icon={ShieldAlert} label="PII Columns" value={ov?.pii_columns ?? '—'} accent="text-red-600" />
        <StatCard icon={Gauge} label="Avg Quality" value={ov?.avg_quality != null ? `${ov.avg_quality}%` : '—'} />
        <StatCard icon={Rows3} label="Rows" value={(ov?.total_rows ?? 0).toLocaleString()} />
      </div>
      <div className="grid md:grid-cols-3 gap-4 mb-6">
        <Card className="p-4"><h4 className="text-sm font-semibold mb-2">Assets by source</h4>
          {ov?.by_source?.length ? <EChart height={200} option={bar(ov.by_source, 'source', '#6366f1')} /> : <Empty message="—" />}</Card>
        <Card className="p-4"><h4 className="text-sm font-semibold mb-2">Sensitivity mix</h4>
          {ov && Object.keys(ov.by_sensitivity || {}).length ? <EChart height={200} option={pie(ov.by_sensitivity)} /> : <Empty message="—" />}</Card>
        <Card className="p-4"><h4 className="text-sm font-semibold mb-2">Quality distribution</h4>
          {ov && Object.values(ov.quality_buckets || {}).some((v: any) => v) ?
            <EChart height={200} option={bar(Object.entries(ov.quality_buckets).map(([k, v]) => ({ source: k, count: v })), 'source', '#10b981')} />
            : <Empty message="Run quality checks to populate" />}</Card>
      </div>

      {/* browse */}
      <div className="grid md:grid-cols-[230px_1fr] gap-5">
        {/* facet sidebar */}
        <div className="space-y-4">
          <Card className="p-4">
            <h4 className="text-xs font-semibold uppercase text-slate-500 mb-2">Source</h4>
            <FacetList items={facets?.sources} valueKey="id" current={sourceId} onPick={(v: string) => reset(() => setSourceId(v))} />
          </Card>
          <Card className="p-4">
            <h4 className="text-xs font-semibold uppercase text-slate-500 mb-2">Type</h4>
            <FacetList items={facets?.asset_types} valueKey="value" current={type} onPick={(v: string) => reset(() => setType(v))} />
          </Card>
          <Card className="p-4">
            <h4 className="text-xs font-semibold uppercase text-slate-500 mb-2">Sensitivity</h4>
            <FacetList items={facets?.sensitivities} valueKey="value" current={sensitivity} onPick={(v: string) => reset(() => setSensitivity(v))} />
          </Card>
        </div>

        {/* results */}
        <div>
          <Card className="p-3 mb-3 flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2 flex-1 min-w-[220px] border border-slate-300 rounded-lg px-3">
              <Search size={16} className="text-slate-400" />
              <input placeholder="Search assets…" value={q} onChange={(e) => reset(() => setQ(e.target.value))} className="py-2 flex-1 outline-none text-sm" />
            </div>
            <select value={sort} onChange={(e) => reset(() => setSort(e.target.value))} className="border border-slate-300 rounded-lg px-3 py-2 text-sm">
              <option value="recent">Recently added</option>
              <option value="name">Name (A–Z)</option>
              <option value="quality">Quality score</option>
            </select>
            <span className="text-sm text-slate-500">{total} results</span>
          </Card>

          <Card className="p-0 overflow-hidden">
            {items.length ? (
              <table className="w-full text-sm">
                <thead><tr className="text-left text-slate-500 border-b border-slate-200 bg-slate-50">
                  {['Asset', 'Type', 'Source', 'Sensitivity', 'Quality', 'Domain'].map((h) => <th key={h} className="py-2 px-4 font-medium">{h}</th>)}
                </tr></thead>
                <tbody>
                  {items.map((a: any) => {
                    const Icon = TYPE_ICON[a.asset_type] ?? Database;
                    return (
                      <tr key={a.id} className="border-b border-slate-100 hover:bg-slate-50">
                        <td className="py-2.5 px-4">
                          <Link to={`/catalog/${a.id}`} className="flex items-center gap-2 text-brand-600 font-medium hover:underline">
                            <Icon size={15} className="text-slate-400" />{a.name}
                          </Link>
                          {a.business_description && <div className="text-xs text-slate-400 ml-6 truncate max-w-md">{a.business_description}</div>}
                        </td>
                        <td className="py-2.5 px-4 text-slate-600">{a.asset_type}</td>
                        <td className="py-2.5 px-4 text-slate-600">{sourceName[a.source_id] ?? '—'}</td>
                        <td className="py-2.5 px-4"><Badge>{a.sensitivity_level}</Badge></td>
                        <td className="py-2.5 px-4">
                          {a.quality_score != null ? (
                            <div className="flex items-center gap-2">
                              <div className="w-16 h-1.5 bg-slate-200 rounded"><div className="h-1.5 rounded bg-green-500" style={{ width: `${a.quality_score}%` }} /></div>
                              <span className="text-xs">{a.quality_score.toFixed(0)}%</span>
                            </div>) : <span className="text-slate-400">—</span>}
                        </td>
                        <td className="py-2.5 px-4 text-slate-500">{a.domain ?? '—'}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            ) : <Empty message="No assets match. Add a source and Scan, or adjust filters." />}
          </Card>

          {total > LIMIT && (
            <div className="flex items-center justify-between mt-3 text-sm">
              <button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - LIMIT))} className="px-3 py-1.5 rounded border border-slate-300 disabled:opacity-40">Previous</button>
              <span className="text-slate-500">{offset + 1}–{Math.min(offset + LIMIT, total)} of {total}</span>
              <button disabled={offset + LIMIT >= total} onClick={() => setOffset(offset + LIMIT)} className="px-3 py-1.5 rounded border border-slate-300 disabled:opacity-40">Next</button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function FacetList({ items, valueKey, current, onPick }: any) {
  if (!items?.length) return <p className="text-xs text-slate-400">—</p>;
  return (
    <div className="space-y-1">
      <button onClick={() => onPick('')} className={`w-full text-left text-sm px-2 py-1 rounded ${!current ? 'bg-brand-50 text-brand-700 font-medium' : 'hover:bg-slate-100'}`}>All</button>
      {items.map((it: any) => (
        <button key={it[valueKey]} onClick={() => onPick(it[valueKey])}
          className={`w-full flex justify-between text-sm px-2 py-1 rounded ${current === it[valueKey] ? 'bg-brand-50 text-brand-700 font-medium' : 'hover:bg-slate-100'}`}>
          <span className="truncate">{it.name ?? it.value}</span><span className="text-slate-400">{it.count}</span>
        </button>
      ))}
    </div>
  );
}
