import { useEffect } from 'react';
import { useAppStore } from '../store/useAppStore';

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
    chat: tg?.initDataUnsafe?.chat ?? null,
    startParam: tg?.initDataUnsafe?.start_param ?? null,
    colorScheme: tg?.colorScheme ?? 'light',
    themeParams: tg?.themeParams ?? {},
    openLink: (url: string) => tg?.openLink(url),
    haptic: tg?.HapticFeedback ?? null,
  };
};

/** Initialize Telegram WebApp and populate global state. Call once in App root. */
export const useTelegramInit = () => {
  const { tg, user, chat, startParam } = useTelegram();
  const { setCurrentUser, setGroupId } = useAppStore();

  useEffect(() => {
    if (tg) {
      tg.ready();
      tg.expand();
    }

    if (user) {
      setCurrentUser(user);
    }

    // Priority: URL param > chat.id > start_param encoding
    const urlParams = new URLSearchParams(window.location.search);
    const urlGroupId = urlParams.get('group_id');

    if (urlGroupId) {
      setGroupId(parseInt(urlGroupId, 10));
    } else if (chat?.id) {
      setGroupId(chat.id);
    } else if (startParam) {
      // Bot passes start_param like "group_-1001234567890"
      const match = startParam.match(/^group_(-?\d+)$/);
      if (match) {
        setGroupId(parseInt(match[1], 10));
      }
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
};
