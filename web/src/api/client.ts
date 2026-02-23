import axios from 'axios';
import type { AxiosError } from 'axios';

const client = axios.create({
  baseURL: '/api',
  timeout: 15000,
});

client.interceptors.request.use((config) => {
  const initData = window.Telegram?.WebApp?.initData ?? '';
  if (initData) {
    config.headers['X-Telegram-InitData'] = initData;
  }
  return config;
});

client.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 403) {
      // Signal access denied globally via custom event
      window.dispatchEvent(new CustomEvent('filmbot:access-denied'));
    }
    return Promise.reject(error);
  },
);

export default client;

/** Extract user-facing error message from API error */
export const getErrorMessage = (error: unknown): string => {
  if (axios.isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: string })?.detail;
    if (detail) return detail;
    if (error.response?.status === 404) return 'Не найдено';
    if (error.response?.status === 409) return 'Уже существует';
    if (error.response?.status === 502) return 'Ошибка Кинопоиска';
    if (error.code === 'ECONNABORTED') return 'Превышено время ожидания';
  }
  return 'Произошла ошибка. Попробуйте ещё раз.';
};
