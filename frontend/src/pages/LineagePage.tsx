import { useQuery } from '@tanstack/react-query';
import ReactFlow, { Background, Controls, type Node, type Edge } from 'reactflow';
import 'reactflow/dist/style.css';
import { lineageApi } from '../lib/api';
import { PageHeader, Card, Empty } from '../components/ui';

export default function LineagePage() {
  const { data, isLoading } = useQuery({ queryKey: ['lineage'], queryFn: lineageApi.graph });

  const nodes: Node[] = (data?.nodes ?? []).map((n: any, i: number) => ({
    id: n.id,
    data: { label: `${n.name}\n(${n.asset_type})` },
    position: { x: (i % 5) * 220, y: Math.floor(i / 5) * 120 },
    style: { padding: 10, borderRadius: 8, border: '1px solid #c7d2fe', background: '#eef2ff', fontSize: 12, whiteSpace: 'pre' },
  }));
  const edges: Edge[] = (data?.edges ?? []).map((e: any) => ({
    id: e.id, source: e.source, target: e.target, animated: true, label: e.transformation ?? undefined,
  }));

  return (
    <div>
      <PageHeader title="Data Lineage" subtitle="End-to-end source → transformation → target flow" />
      <Card className="p-2" >
        <div style={{ height: 600 }}>
          {isLoading ? <Empty message="Loading lineage…" />
            : nodes.length ? (
              <ReactFlow nodes={nodes} edges={edges} fitView>
                <Background /><Controls />
              </ReactFlow>
            ) : <Empty message="No lineage yet. Connect a GitHub ETL source and scan to extract lineage." />}
        </div>
      </Card>
    </div>
  );
}
