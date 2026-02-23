import React, { useState } from 'react';

interface UserAvatarProps {
  telegramId: number | null;
  username?: string | null;
  firstName?: string | null;
  size?: number;
}

const PALETTE = [
  '#e74c3c', '#e67e22', '#f39c12', '#27ae60',
  '#1abc9c', '#2980b9', '#8e44ad', '#c0392b',
];

const getColor = (id: number | null): string =>
  PALETTE[Math.abs(id ?? 0) % PALETTE.length];

export const UserAvatar: React.FC<UserAvatarProps> = ({
  telegramId,
  username,
  firstName,
  size = 36,
}) => {
  const [hasError, setHasError] = useState(false);

  const initials = (firstName?.[0] || username?.[0] || '?').toUpperCase();
  const fontSize = Math.round(size * 0.42);

  if (!telegramId || hasError) {
    return (
      <div
        style={{
          width: size,
          height: size,
          borderRadius: '50%',
          backgroundColor: getColor(telegramId),
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#fff',
          fontSize,
          fontWeight: 700,
          flexShrink: 0,
          userSelect: 'none',
        }}
      >
        {initials}
      </div>
    );
  }

  return (
    <img
      src={`/api/users/${telegramId}/avatar`}
      alt={username || firstName || ''}
      onError={() => setHasError(true)}
      style={{
        width: size,
        height: size,
        borderRadius: '50%',
        objectFit: 'cover',
        flexShrink: 0,
      }}
    />
  );
};
