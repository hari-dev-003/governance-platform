import { useEffect } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../store/auth';

export default function ProtectedRoute({ children }: { children: JSX.Element }) {
  const { user, loading, hydrate } = useAuth();
  useEffect(() => { if (loading) hydrate(); }, [loading, hydrate]);
  if (loading) return <div className="h-screen grid place-items-center text-slate-400">Loading…</div>;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}
