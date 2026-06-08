import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ShieldAlert } from 'lucide-react';
import { useAuth } from '../store/auth';

export default function LoginPage() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState('admin@local');
  const [password, setPassword] = useState('admin123');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setError('');
    try { await login(email, password); nav('/'); }
    catch { setError('Invalid credentials'); }
    finally { setBusy(false); }
  }

  return (
    <div className="min-h-screen grid place-items-center bg-slate-900">
      <form onSubmit={submit} className="bg-white rounded-2xl shadow-xl p-8 w-[380px]">
        <div className="flex items-center gap-2 mb-6">
          <ShieldAlert className="text-brand-600" />
          <h1 className="text-xl font-bold">Data + AI Governance</h1>
        </div>
        <label className="block text-sm font-medium text-slate-600 mb-1">Email</label>
        <input value={email} onChange={(e) => setEmail(e.target.value)}
          className="w-full border border-slate-300 rounded-lg px-3 py-2 mb-4" />
        <label className="block text-sm font-medium text-slate-600 mb-1">Password</label>
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
          className="w-full border border-slate-300 rounded-lg px-3 py-2 mb-4" />
        {error && <div className="text-red-600 text-sm mb-3">{error}</div>}
        <button disabled={busy} className="w-full bg-brand-600 text-white py-2 rounded-lg font-medium hover:bg-brand-700 disabled:opacity-50">
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
        <p className="text-xs text-slate-400 mt-4 text-center">Default admin: admin@local / admin123</p>
      </form>
    </div>
  );
}
