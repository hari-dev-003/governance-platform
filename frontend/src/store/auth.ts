import { create } from 'zustand';
import { authApi, tokenStore, type SessionUser } from '../lib/api';

interface AuthState {
  user: SessionUser | null;
  loading: boolean;
  login: (u: string, p: string) => Promise<void>;
  logout: () => void;
  hydrate: () => Promise<void>;
}

export const useAuth = create<AuthState>((set) => ({
  user: null,
  loading: true,
  async login(username, password) {
    const res = await authApi.login(username, password);
    tokenStore.set(res.access_token);
    const me = await authApi.me();
    set({ user: me });
  },
  logout() {
    tokenStore.clear();
    set({ user: null });
    location.href = '/login';
  },
  async hydrate() {
    if (!tokenStore.get()) { set({ user: null, loading: false }); return; }
    try { set({ user: await authApi.me(), loading: false }); }
    catch { tokenStore.clear(); set({ user: null, loading: false }); }
  },
}));
