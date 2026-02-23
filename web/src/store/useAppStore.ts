import { create } from 'zustand';
import type { TelegramUser, Session } from '../types';

interface AppState {
  currentUser: TelegramUser | null;
  isAdmin: boolean;
  isAccessDenied: boolean;
  currentSession: Session | null;

  setCurrentUser: (user: TelegramUser) => void;
  setIsAdmin: (admin: boolean) => void;
  setAccessDenied: (denied: boolean) => void;
  setCurrentSession: (session: Session | null) => void;
}

export const useAppStore = create<AppState>((set) => ({
  currentUser: null,
  isAdmin: false,
  isAccessDenied: false,
  currentSession: null,

  setCurrentUser: (user) => set({ currentUser: user }),
  setIsAdmin: (admin) => set({ isAdmin: admin }),
  setAccessDenied: (denied) => set({ isAccessDenied: denied }),
  setCurrentSession: (session) => set({ currentSession: session }),
}));
