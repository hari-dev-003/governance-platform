import type { ReactNode } from 'react';
import { Link, NavLink } from 'react-router-dom';
import {
  LayoutDashboard, Plug, Database, GitBranch, ShieldCheck, Activity,
  KeyRound, Brain, AlertTriangle, ScrollText, History, LogOut, ShieldAlert,
} from 'lucide-react';
import { useAuth } from '../store/auth';

const SECTIONS: { title: string; items: { to: string; label: string; icon: any }[] }[] = [
  { title: 'Overview', items: [{ to: '/', label: 'Dashboard', icon: LayoutDashboard }] },
  { title: 'Data Governance', items: [
    { to: '/sources', label: 'Sources', icon: Plug },
    { to: '/catalog', label: 'Catalog', icon: Database },
    { to: '/lineage', label: 'Lineage', icon: GitBranch },
    { to: '/classification', label: 'Classification & Privacy', icon: ShieldCheck },
    { to: '/quality', label: 'Quality', icon: Activity },
    { to: '/access', label: 'Access Requests', icon: KeyRound },
  ]},
  { title: 'AI Governance', items: [
    { to: '/ai-models', label: 'Model Registry', icon: Brain },
    { to: '/monitoring', label: 'Monitoring', icon: AlertTriangle },
  ]},
  { title: 'Compliance', items: [
    { to: '/compliance', label: 'Compliance', icon: ScrollText },
    { to: '/audit', label: 'Audit Trail', icon: History },
  ]},
];

const ROLE_BADGE: Record<string, string> = {
  admin: 'bg-red-100 text-red-700', data_steward: 'bg-blue-100 text-blue-700',
  ai_risk_officer: 'bg-purple-100 text-purple-700', viewer: 'bg-slate-100 text-slate-700',
};

export default function Layout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  return (
    <div className="flex h-screen bg-slate-50">
      <aside className="w-64 bg-slate-900 text-white flex flex-col shrink-0">
        <Link to="/" className="p-5 border-b border-slate-800 flex items-center gap-2">
          <ShieldAlert className="text-brand-500" />
          <div>
            <div className="font-bold leading-tight">Data + AI Governance</div>
            <div className="text-[10px] text-slate-400">Catalog · Lineage · AI Risk · Compliance</div>
          </div>
        </Link>
        <nav className="flex-1 overflow-y-auto p-3 space-y-4">
          {SECTIONS.map((s) => (
            <div key={s.title}>
              <div className="text-[10px] uppercase tracking-wider text-slate-500 px-3 mb-1">{s.title}</div>
              <div className="space-y-0.5">
                {s.items.map(({ to, label, icon: Icon }) => (
                  <NavLink key={to} to={to} end={to === '/'}
                    className={({ isActive }) => [
                      'flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition',
                      isActive ? 'bg-brand-600 text-white' : 'text-slate-300 hover:bg-slate-800',
                    ].join(' ')}>
                    <Icon size={16} /> {label}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>
        {user && (
          <div className="p-4 border-t border-slate-800 flex items-center justify-between">
            <div className="min-w-0">
              <div className="text-sm truncate">{user.email}</div>
              <span className={`inline-block mt-1 text-[10px] px-2 py-0.5 rounded-full font-bold uppercase ${ROLE_BADGE[user.role] ?? ROLE_BADGE.viewer}`}>
                {user.role}
              </span>
            </div>
            <button onClick={logout} title="Sign out" className="p-2 rounded hover:bg-slate-800 text-slate-300">
              <LogOut size={18} />
            </button>
          </div>
        )}
      </aside>
      <main className="flex-1 overflow-auto">
        <div className="p-8 max-w-[1500px] mx-auto">{children}</div>
      </main>
    </div>
  );
}
