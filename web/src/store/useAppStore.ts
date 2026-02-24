import { create } from 'zustand';
import type { TelegramUser, Session } from '../types';

interface AppState {
  currentUser: TelegramUser | null;
  isAdmin: boolean;
  isAccessDenied: boolean;
  isAuthLoading: boolean;
  currentSession: Session | null;

  setCurrentUser: (user: TelegramUser) => void;
  setIsAdmin: (admin: boolean) => void;
  setAccessDenied: (denied: boolean) => void;
  setAuthLoading: (loading: boolean) => void;
  setCurrentSession: (session: Session | null) => void;
}

export const useAppStore = create<AppState>((set) => ({
  currentUser: null,
  isAdmin: false,
  isAccessDenied: false,
  isAuthLoading: true,
  currentSession: null,

  setCurrentUser: (user) => set({ currentUser: user }),
  setIsAdmin: (admin) => set({ isAdmin: admin }),
  setAccessDenied: (denied) => set({ isAccessDenied: denied }),
  setAuthLoading: (loading) => set({ isAuthLoading: loading }),
  setCurrentSession: (session) => set({ currentSession: session }),
}));
