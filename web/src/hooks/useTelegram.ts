import { useEffect } from 'react';
import { useAppStore } from '../store/useAppStore';
import { getMe } from '../api/users';

// Extend window with Telegram WebApp types
declare global {
  interface Window {
    Telegram?: {
      WebApp: TelegramWebApp;
    };
  }
}

interface TelegramWebApp {
  initData: string;
  initDataUnsafe: {
    user?: {
      id: number;
      first_name: string;
      last_name?: string;
      username?: string;
      language_code?: string;
    };
    chat?: {
      id: number;
      type: string;
      title?: string;
    };
    start_param?: string;
    auth_date?: number;
    hash?: string;
  };
  themeParams: {
    bg_color?: string;
    text_color?: string;
    hint_color?: string;
    link_color?: string;
    button_color?: string;
    button_text_color?: string;
    secondary_bg_color?: string;
  };
  colorScheme: 'light' | 'dark';
  viewportHeight: number;
  ready: () => void;
  expand: () => void;
  close: () => void;
  openLink: (url: string, options?: { try_instant_view?: boolean }) => void;
  showAlert: (message: string, callback?: () => void) => void;
  showConfirm: (message: string, callback: (ok: boolean) => void) => void;
  MainButton: {
    text: string;
    color: string;
    textColor: string;
    isVisible: boolean;
    isActive: boolean;
    setText: (text: string) => void;
    onClick: (callback: () => void) => void;
    offClick: (callback: () => void) => void;
    show: () => void;
    hide: () => void;
    enable: () => void;
    disable: () => void;
  };
  HapticFeedback: {
    impactOccurred: (style: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft') => void;
    notificationOccurred: (type: 'error' | 'success' | 'warning') => void;
    selectionChanged: () => void;
  };
}

export const useTelegram = () => {
  const tg = window.Telegram?.WebApp;
  return {
    tg,
    user: tg?.initDataUnsafe?.user ?? null,
    colorScheme: tg?.colorScheme ?? 'light',
    themeParams: tg?.themeParams ?? {},
    openLink: (url: string) => tg?.openLink(url),
    haptic: tg?.HapticFeedback ?? null,
  };
};

/** Initialize Telegram WebApp and populate global state. Call once in App root. */
export const useTelegramInit = () => {
  const { tg, user } = useTelegram();
  const { setCurrentUser, setIsAdmin, setAuthLoading } = useAppStore();

  useEffect(() => {
    if (tg) {
      tg.ready();
      tg.expand();
    }

    if (user) {
      setCurrentUser(user);
    }

    getMe()
      .then(({ is_admin }) => {
        setIsAdmin(is_admin);
        setAuthLoading(false);
      })
      .catch(() => {
        setAuthLoading(false);
        // 403 → filmbot:access-denied event handles it
      });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
};
