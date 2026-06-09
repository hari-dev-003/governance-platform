import { useMemo, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import ReactFlow, { Background, Controls, MarkerType, type Node, type Edge } from 'reactflow';
import 'reactflow/dist/style.css';
import dagre from 'dagre';
import { lineageApi } from '../lib/api';
import { PageHeader, Card, Empty, Button } from '../components/ui';

type Level = 'table' | 'column';
const NODE_W = 200;
const NODE_H = 46;

// stable pastel colour per table name (for grouping column nodes)
function tableColor(key: string): string {
  let h = 0;
  for (let i = 0; i < key.length; i++) h = (h * 31 + key.charCodeAt(i)) % 360;
  return `hsl(${h} 70% 92%)`;
}
function tableBorder(key: string): string {
  let h = 0;
  for (let i = 0; i < key.length; i++) h = (h * 31 + key.charCodeAt(i)) % 360;
  return `hsl(${h} 60% 55%)`;
}

// label + group from a column node's external_id (….table.column)
function colLabel(n: any): { label: string; group: string } {
  const parts = String(n.external_id || n.name).split('.');
  const col = parts[parts.length - 1];
  const tbl = parts.length >= 2 ? parts[parts.length - 2] : '';
  return { label: tbl ? `${tbl}.${col}` : col, group: tbl || n.name };
}

function dagreLayout(nodes: Node[], edges: Edge[]): Node[] {
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: 'LR', nodesep: 28, ranksep: 130, marginx: 20, marginy: 20 });
  g.setDefaultEdgeLabel(() => ({}));
  nodes.forEach((n) => g.setNode(n.id, { width: NODE_W, height: NODE_H }));
  edges.forEach((e) => g.setEdge(e.source, e.target));
  dagre.layout(g);
  return nodes.map((n) => {
    const p = g.node(n.id);
    return { ...n, position: { x: p.x - NODE_W / 2, y: p.y - NODE_H / 2 } };
  });
}

export default function LineagePage() {
  const qc = useQueryClient();
  const [level, setLevel] = useState<Level>('table');
  const { data, isLoading } = useQuery({ queryKey: ['lineage', level], queryFn: () => lineageApi.graph(level) });
  const rebuild = useMutation({
    mutationFn: lineageApi.rebuild,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['lineage'] }); },
  });

  const { nodes, edges } = useMemo(() => {
    const rawNodes: Node[] = (data?.nodes ?? []).map((n: any) => {
      if (level === 'column') {
        const { label, group } = colLabel(n);
        return {
          id: n.id, data: { label }, position: { x: 0, y: 0 },
          style: { width: NODE_W, height: NODE_H, borderRadius: 8, fontSize: 11,
            background: tableColor(group), border: `1.5px solid ${tableBorder(group)}`,
            display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 4 },
        };
      }
      return {
        id: n.id, data: { label: `${n.name}\n(${n.asset_type})` }, position: { x: 0, y: 0 },
        style: { width: NODE_W, height: NODE_H, borderRadius: 8, fontSize: 12, whiteSpace: 'pre',
          background: '#eef2ff', border: '1.5px solid #6366f1',
          display: 'flex', alignItems: 'center', justifyContent: 'center', textAlign: 'center' as const },
      };
    });
    const rawEdges: Edge[] = (data?.edges ?? []).map((e: any) => ({
      id: e.id, source: e.source, target: e.target, type: 'smoothstep', animated: false,
      markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16, color: '#94a3b8' },
      style: { stroke: '#94a3b8', strokeWidth: 1.5 },
      label: level === 'table' && e.transformation ? String(e.transformation).split('/').pop() : undefined,
      labelStyle: { fontSize: 10, fill: '#64748b' },
    }));
    return { nodes: dagreLayout(rawNodes, rawEdges), edges: rawEdges };
  }, [data, level]);

  return (
    <div>
      <PageHeader title="Data Lineage" subtitle="From connected ETL scripts — table and column level"
        actions={
          <div className="flex gap-2">
            <div className="flex rounded-lg border border-slate-300 overflow-hidden">
              {(['table', 'column'] as Level[]).map((l) => (
                <button key={l} onClick={() => setLevel(l)}
                  className={`px-3 py-2 text-sm capitalize ${level === l ? 'bg-brand-600 text-white' : 'bg-white text-slate-600'}`}>
                  {l}
                </button>
              ))}
            </div>
            <Button onClick={() => rebuild.mutate()} disabled={rebuild.isPending}>
              {rebuild.isPending ? 'Rebuilding…' : 'Rebuild Lineage'}</Button>
          </div>
        } />
      {rebuild.data && (
        <div className="mb-4 text-sm bg-slate-100 rounded-lg px-4 py-2">
          Rebuilt: {rebuild.data.edges_created} edges from {rebuild.data.assets_with_lineage} ETL scripts.
        </div>
      )}
      <Card className="p-2">
        <div style={{ height: 620 }}>
          {isLoading ? <Empty message="Loading lineage…" />
            : nodes.length ? (
              <ReactFlow nodes={nodes} edges={edges} fitView minZoom={0.2}
                proOptions={{ hideAttribution: true }}>
                <Background /><Controls />
              </ReactFlow>
            ) : <Empty message={level === 'column'
              ? 'No column lineage yet. Ensure source + target tables are cataloged, connect the ETL repo, Scan, then Rebuild.'
              : 'No lineage yet. Connect an ETL repository, Scan, then Rebuild Lineage.'} />}
        </div>
      </Card>
    </div>
  );
}
