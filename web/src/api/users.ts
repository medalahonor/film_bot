import client from './client';

export interface MeResponse {
  telegram_id: number;
  first_name: string | null;
  last_name: string | null;
  username: string | null;
  is_admin: boolean;
  is_allowed: boolean;
}

export const getMe = (): Promise<MeResponse> =>
  client.get<MeResponse>('/users/me').then((r) => r.data);
