import type { ReactNode } from 'react';

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="flex items-start justify-between mb-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">{title}</h1>
        {subtitle && <p className="text-sm text-slate-500 mt-1">{subtitle}</p>}
      </div>
      {actions && <div className="flex gap-2">{actions}</div>}
    </div>
  );
}

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`bg-white rounded-xl border border-slate-200 shadow-sm ${className}`}>{children}</div>;
}

export function Stat({ label, value, accent = 'text-slate-900' }: { label: string; value: ReactNode; accent?: string }) {
  return (
    <Card className="p-5">
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className={`text-3xl font-bold mt-1 ${accent}`}>{value}</div>
    </Card>
  );
}

export function Button({ children, onClick, variant = 'primary', type = 'button', disabled }:
  { children: ReactNode; onClick?: () => void; variant?: 'primary' | 'ghost' | 'danger'; type?: 'button' | 'submit'; disabled?: boolean }) {
  const styles = {
    primary: 'bg-brand-600 text-white hover:bg-brand-700',
    ghost: 'bg-white border border-slate-300 text-slate-700 hover:bg-slate-50',
    danger: 'bg-red-600 text-white hover:bg-red-700',
  }[variant];
  return (
    <button type={type} onClick={onClick} disabled={disabled}
      className={`px-4 py-2 rounded-lg text-sm font-medium transition disabled:opacity-50 ${styles}`}>
      {children}
    </button>
  );
}

const TONE: Record<string, string> = {
  public: 'bg-slate-100 text-slate-700', internal: 'bg-blue-100 text-blue-700',
  confidential: 'bg-amber-100 text-amber-800', restricted: 'bg-red-100 text-red-700',
  unclassified: 'bg-slate-100 text-slate-500',
  high: 'bg-red-100 text-red-700', limited: 'bg-amber-100 text-amber-800',
  minimal: 'bg-green-100 text-green-700', unacceptable: 'bg-red-200 text-red-900',
  pass: 'bg-green-100 text-green-700', fail: 'bg-red-100 text-red-700',
  warning: 'bg-amber-100 text-amber-800', critical: 'bg-red-100 text-red-700',
  approved: 'bg-green-100 text-green-700', pending: 'bg-amber-100 text-amber-800',
  pending_approval: 'bg-amber-100 text-amber-800', draft: 'bg-slate-100 text-slate-600',
  connected: 'bg-green-100 text-green-700', error: 'bg-red-100 text-red-700',
  open: 'bg-red-100 text-red-700', acknowledged: 'bg-blue-100 text-blue-700',
};

export function Badge({ children }: { children: string }) {
  const tone = TONE[children?.toLowerCase?.()] ?? 'bg-slate-100 text-slate-700';
  return <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-semibold ${tone}`}>{children}</span>;
}

export function Table({ head, children }: { head: string[]; children: ReactNode }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-slate-500 border-b border-slate-200">
            {head.map((h) => <th key={h} className="py-2 px-3 font-medium">{h}</th>)}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

export function Empty({ message }: { message: string }) {
  return <div className="text-center py-12 text-slate-400 text-sm">{message}</div>;
}
