import { create } from "zustand";
import { api }    from "@/lib/api";
import type { User } from "@/types";

interface AuthState {
  user:      User | null;
  token:     string | null;
  isLoading: boolean;
  error:     string | null;
  /** @deprecated use isLoading */ loading: boolean;
  login:     (username: string, password: string, tenant_id: string) => Promise<void>;
  logout:    () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user:      null,
  token:     typeof window !== "undefined" ? localStorage.getItem("hai_token") : null,
  isLoading: false,
  loading:   false,
  error:     null,

  login: async (username, password, tenant_id) => {
    set({ isLoading: true, loading: true, error: null });
    try {
      const tok = await api.login(username, password, tenant_id);
      set({ user: { username, tenant_id }, token: tok, isLoading: false, loading: false });
    } catch (err: any) {
      set({ isLoading: false, loading: false, error: err?.message ?? "Login failed" });
      throw err;
    }
  },

  logout: () => {
    api.logout();
    set({ user: null, token: null, error: null });
  },
}));
