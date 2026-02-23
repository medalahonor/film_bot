import client from './client';

export interface MeResponse {
  telegram_id: number;
  is_admin: boolean;
  is_allowed: boolean;
}

export const getMe = (): Promise<MeResponse> =>
  client.get<MeResponse>('/users/me').then((r) => r.data);
