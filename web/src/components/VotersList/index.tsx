import React from 'react';
import { UserAvatar } from '../UserAvatar';
import { formatUserName } from '../../types';
import type { VoterInfo } from '../../types';

interface VotersListProps {
  voters: VoterInfo[];
}

export const VotersList: React.FC<VotersListProps> = ({ voters }) => {
  if (voters.length === 0) return null;

  return (
    <div style={{ padding: '4px 16px 8px 88px' }}>
      <div style={{
        fontSize: 11,
        color: 'var(--tg-theme-hint-color, #999)',
        marginBottom: 4,
      }}>
        Проголосовали
      </div>
      <div style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: 6,
      }}>
        {voters.map((v) => (
          <div
            key={v.telegram_id}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              fontSize: 12,
              color: 'var(--tg-theme-hint-color, #999)',
            }}
          >
            <UserAvatar
              telegramId={v.telegram_id}
              username={v.username}
              firstName={v.first_name}
              size={20}
            />
            <span>{formatUserName(v.first_name, v.last_name, v.username)}</span>
          </div>
        ))}
      </div>
    </div>
  );
};
