import { useMemo, useState, useEffect, useRef, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import ReactFlow, {
  Background, Controls, MiniMap, Handle, Position, MarkerType,
  useNodesState, useEdgesState, type Node, type Edge,
} from 'reactflow';
import 'reactflow/dist/style.css';
import dagre from 'dagre';
import { lineageApi } from '../lib/api';
import { PageHeader, Card, Empty, Button } from '../components/ui';

type Level = 'table' | 'column';
const ROW_H = 22, HEAD_H = 30, CARD_W = 230;
const DIM = 0.12;

function TableCardNode({ data }: any) {
  return (
    <div style={{ width: CARD_W, border: `1.5px solid ${data.faded ? '#cbd5e1' : '#6366f1'}`,
      borderRadius: 10, background: '#fff', boxShadow: '0 1px 4px rgba(15,23,42,.08)', fontSize: 11, overflow: 'hidden' }}>
      <div style={{ background: data.faded ? '#94a3b8' : '#6366f1', color: '#fff', padding: '6px 10px', fontWeight: 600, fontSize: 12 }}>{data.table}</div>
      <div>
        {data.columns.map((c: any, i: number) => (
          <div key={c.id} style={{ position: 'relative', height: ROW_H, lineHeight: `${ROW_H}px`, padding: '0 12px',
            borderTop: i ? '1px solid #f1f5f9' : 'none', color: '#334155' }}>
            {c.name}
            <Handle type="target" position={Position.Left} id={c.id} style={{ top: HEAD_H + i * ROW_H + ROW_H / 2, background: '#94a3b8', width: 7, height: 7 }} />
            <Handle type="source" position={Position.Right} id={c.id} style={{ top: HEAD_H + i * ROW_H + ROW_H / 2, background: '#6366f1', width: 7, height: 7 }} />
          </div>
        ))}
      </div>
    </div>
  );
}
const NODE_TYPES = { tableCard: TableCardNode };
const MINIMAP_COLOR = () => '#c7d2fe';

function basename(s?: string) { return s ? String(s).split('/').pop() : ''; }

function dagreLayout(nodes: Node[], edges: Edge[], dims: Record<string, { w: number; h: number }>): Node[] {
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: 'LR', nodesep: 45, ranksep: 200, marginx: 30, marginy: 30 });
  g.setDefaultEdgeLabel(() => ({}));
  nodes.forEach((n) => g.setNode(n.id, { width: dims[n.id]?.w ?? CARD_W, height: dims[n.id]?.h ?? 50 }));
  edges.forEach((e) => g.setEdge(e.source, e.target));
  dagre.layout(g);
  return nodes.map((n) => {
    const p = g.node(n.id); const d = dims[n.id] ?? { w: CARD_W, h: 50 };
    return { ...n, position: { x: p.x - d.w / 2, y: p.y - d.h / 2 } };
  });
}

export default function LineagePage() {
  const qc = useQueryClient();
  const [level, setLevel] = useState<Level>('table');
  const [focusId, setFocusId] = useState<string | null>(null);
  const [hoverId, setHoverId] = useState<string | null>(null);
  const { data, isLoading } = useQuery({ queryKey: ['lineage', level], queryFn: () => lineageApi.graph(level) });
  const rebuild = useMutation({ mutationFn: lineageApi.rebuild, onSuccess: () => qc.invalidateQueries({ queryKey: ['lineage'] }) });
  const nodeTypes = useMemo(() => NODE_TYPES, []);

  // ---- base graph (laid out once per data/level): nodes + MERGED edges + adjacency ----
  const base = useMemo(() => {
    const dims: Record<string, { w: number; h: number }> = {};
    const labels: Record<string, string> = {};
    let rawNodes: Node[] = [];
    type RawEdge = { id: string; source: string; target: string; sourceHandle?: string; targetHandle?: string; transforms: Set<string> };
    const merged: Record<string, RawEdge> = {};

    const addEdge = (key: string, e: Omit<RawEdge, 'transforms'>, transform?: string) => {
      const m = merged[key] ?? (merged[key] = { ...e, transforms: new Set() });
      if (transform) m.transforms.add(basename(transform)!);
    };

    if (level === 'column') {
      const tables: Record<string, { id: string; name: string; columns: any[] }> = {};
      const colToTable: Record<string, string> = {};
      (data?.nodes ?? []).forEach((n: any) => {
        const ext: string = n.external_id || n.name, nm: string = n.name;
        const key = ext.endsWith('.' + nm) ? ext.slice(0, ext.length - nm.length - 1) : ext;
        const tname = key.split('.').pop() || key;
        if (!tables[key]) tables[key] = { id: 't:' + key, name: tname, columns: [] };
        tables[key].columns.push({ id: n.id, name: nm });
        colToTable[n.id] = tables[key].id;
      });
      rawNodes = Object.values(tables).map((t) => {
        dims[t.id] = { w: CARD_W, h: HEAD_H + t.columns.length * ROW_H + 2 }; labels[t.id] = t.name;
        return { id: t.id, type: 'tableCard', data: { table: t.name, columns: t.columns }, position: { x: 0, y: 0 } };
      });
      (data?.edges ?? []).forEach((e: any) => {
        const s = colToTable[e.source], t = colToTable[e.target];
        if (!s || !t) return;
        addEdge(`${s}|${e.source}|${t}|${e.target}`, { id: e.id, source: s, target: t, sourceHandle: e.source, targetHandle: e.target }, e.transformation);
      });
    } else {
      rawNodes = (data?.nodes ?? []).map((n: any) => {
        dims[n.id] = { w: CARD_W, h: 50 }; labels[n.id] = n.name;
        return { id: n.id, data: { label: n.name }, position: { x: 0, y: 0 } };
      });
      (data?.edges ?? []).forEach((e: any) => addEdge(`${e.source}|${e.target}`, { id: e.id, source: e.source, target: e.target }, e.transformation));
    }

    const rfEdges: Edge[] = Object.values(merged).map((m) => ({
      id: m.id, source: m.source, target: m.target, sourceHandle: m.sourceHandle, targetHandle: m.targetHandle,
      type: 'smoothstep', data: { transform: Array.from(m.transforms).join(' + ') },
    }));
    // adjacency for focus / hover
    const up: Record<string, Set<string>> = {}, down: Record<string, Set<string>> = {};
    rfEdges.forEach((e) => { (down[e.source] ??= new Set()).add(e.target); (up[e.target] ??= new Set()).add(e.source); });
    const lineageOf = (id: string) => {
      const seen = new Set<string>([id]);
      const walk = (start: string, adj: Record<string, Set<string>>) => {
        const st = [start]; while (st.length) { const c = st.pop()!; (adj[c] ?? new Set()).forEach((n) => { if (!seen.has(n)) { seen.add(n); st.push(n); } }); }
      };
      walk(id, up); walk(id, down); return seen;
    };
    return { rfNodes: dagreLayout(rawNodes, rfEdges, dims), rfEdges, labels, lineageOf, count: rawNodes.length };
  }, [data, level]);

  // ---- displayed nodes/edges (focus filter + hover/focus styling) ----
  const display = useMemo(() => {
    const active = hoverId || focusId;
    const set = active ? base.lineageOf(active) : null;
    let ns = base.rfNodes, es = base.rfEdges;
    if (focusId) { const f = base.lineageOf(focusId); ns = ns.filter((n) => f.has(n.id)); es = es.filter((e) => f.has(e.source) && f.has(e.target)); }
    const nodes: Node[] = ns.map((n) => {
      const lit = !set || set.has(n.id); const isCol = n.type === 'tableCard';
      return {
        ...n,
        data: isCol ? { ...n.data, faded: !lit } : n.data,
        style: isCol ? { opacity: lit ? 1 : DIM }
          : { width: CARD_W, height: 50, borderRadius: 10, fontSize: 12, background: '#fff',
              border: `1.5px solid ${focusId === n.id ? '#4338ca' : lit ? '#6366f1' : '#cbd5e1'}`,
              boxShadow: '0 1px 4px rgba(15,23,42,.08)', display: 'flex', alignItems: 'center',
              justifyContent: 'center', textAlign: 'center' as const, opacity: lit ? 1 : DIM, fontWeight: focusId === n.id ? 700 : 500 },
      };
    });
    const edges: Edge[] = es.map((e) => {
      const lit = !set || (set.has(e.source) && set.has(e.target));
      return {
        ...e, animated: false,
        markerEnd: { type: MarkerType.ArrowClosed, width: 15, height: 15, color: lit ? '#6366f1' : '#cbd5e1' },
        style: { stroke: lit ? '#6366f1' : '#e2e8f0', strokeWidth: lit ? 1.8 : 1, opacity: lit ? 1 : 0.4 },
        label: level === 'table' && lit && e.data?.transform ? e.data.transform : undefined,
        labelStyle: { fontSize: 10, fill: '#64748b' }, labelBgStyle: { fill: '#fff', fillOpacity: 0.8 },
      };
    });
    return { nodes, edges };
  }, [base, focusId, hoverId, level]);

  // ---- controlled state (prevents flicker) ----
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  useEffect(() => { setNodes(display.nodes); setEdges(display.edges); }, [display, setNodes, setEdges]);

  // ---- fit only on STRUCTURAL change (data/level/focus) — never on hover ----
  const rf = useRef<any>(null);
  const structKey = `${level}|${focusId ?? ''}|${base.count}`;
  useEffect(() => {
    const id = setTimeout(() => rf.current?.fitView({ padding: 0.2, duration: 250 }), 60);
    return () => clearTimeout(id);
  }, [structKey]);

  const onNodeClick = useCallback((_: any, n: Node) => setFocusId((c) => (c === n.id ? null : n.id)), []);
  const focusLabel = focusId ? base.labels[focusId] : null;

  return (
    <div>
      <PageHeader title="Data Lineage" subtitle="SQL + Spark transformations · click to focus · hover to trace"
        actions={
          <div className="flex gap-2">
            <div className="flex rounded-lg border border-slate-300 overflow-hidden">
              {(['table', 'column'] as Level[]).map((l) => (
                <button key={l} onClick={() => { setLevel(l); setFocusId(null); }}
                  className={`px-3 py-2 text-sm capitalize ${level === l ? 'bg-brand-600 text-white' : 'bg-white text-slate-600'}`}>{l}</button>
              ))}
            </div>
            <Button onClick={() => rebuild.mutate()} disabled={rebuild.isPending}>{rebuild.isPending ? 'Rebuilding…' : 'Rebuild Lineage'}</Button>
          </div>
        } />
      {focusLabel && (
        <div className="mb-3 flex items-center gap-3 text-sm bg-brand-50 text-brand-700 rounded-lg px-4 py-2">
          Focused on <b>{focusLabel}</b> — upstream &amp; downstream lineage.
          <button onClick={() => setFocusId(null)} className="ml-auto px-2 py-0.5 rounded border border-brand-300 text-xs">Clear focus</button>
        </div>
      )}
      {rebuild.data && <div className="mb-3 text-sm bg-slate-100 rounded-lg px-4 py-2">Rebuilt: {rebuild.data.edges_created} edges.</div>}
      <Card className="p-0 overflow-hidden">
        <div style={{ height: 660 }}>
          {isLoading ? <Empty message="Loading lineage…" />
            : base.count ? (
              <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes}
                onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
                onInit={(inst) => { rf.current = inst; }}
                onNodeClick={onNodeClick}
                onNodeMouseEnter={(_, n) => setHoverId(n.id)}
                onNodeMouseLeave={() => setHoverId(null)}
                onPaneClick={() => setFocusId(null)}
                minZoom={0.1} maxZoom={2} proOptions={{ hideAttribution: true }}>
                <Background color="#eef2f7" gap={18} />
                <Controls showInteractive={false} />
                <MiniMap pannable zoomable nodeColor={MINIMAP_COLOR} maskColor="rgba(241,245,249,.7)" />
              </ReactFlow>
            ) : <Empty message="No lineage yet. Scan an etl_repo source (SQL) and/or run the Spark job, then Rebuild." />}
        </div>
      </Card>
    </div>
  );
}
