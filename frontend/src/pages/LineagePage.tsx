import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import ReactFlow, { Background, Controls, type Node, type Edge } from 'reactflow';
import 'reactflow/dist/style.css';
import { lineageApi } from '../lib/api';
import { PageHeader, Card, Empty, Button } from '../components/ui';

export default function LineagePage() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ['lineage'], queryFn: lineageApi.graph });
  const rebuild = useMutation({
    mutationFn: lineageApi.rebuild,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['lineage'] }),
  });

  const nodes: Node[] = (data?.nodes ?? []).map((n: any, i: number) => ({
    id: n.id,
    data: { label: `${n.name}\n(${n.asset_type})` },
    position: { x: (i % 5) * 220, y: Math.floor(i / 5) * 130 },
    style: { padding: 10, borderRadius: 8, border: '1px solid #c7d2fe', background: '#eef2ff', fontSize: 12, whiteSpace: 'pre' },
  }));
  const edges: Edge[] = (data?.edges ?? []).map((e: any) => ({
    id: e.id, source: e.source, target: e.target, animated: true,
    label: e.transformation ? e.transformation.split('/').pop() : undefined,
  }));

  return (
    <div>
      <PageHeader title="Data Lineage" subtitle="Source → transformation → target, resolved across all connectors"
        actions={<Button onClick={() => rebuild.mutate()} disabled={rebuild.isPending}>
          {rebuild.isPending ? 'Rebuilding…' : 'Rebuild Lineage'}</Button>} />
      {rebuild.data && (
        <div className="mb-4 text-sm bg-slate-100 rounded-lg px-4 py-2">
          Rebuilt: {rebuild.data.edges_created} edges from {rebuild.data.assets_with_lineage} sources (FK + ETL scripts).
        </div>
      )}
      <Card className="p-2">
        <div style={{ height: 600 }}>
          {isLoading ? <Empty message="Loading lineage…" />
            : nodes.length ? (
              <ReactFlow nodes={nodes} edges={edges} fitView>
                <Background /><Controls />
              </ReactFlow>
            ) : <Empty message="No lineage yet. Scan a database (FK lineage) or connect an ETL repository (script lineage), then Rebuild." />}
        </div>
      </Card>
    </div>
  );
}
