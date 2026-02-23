import React from 'react';
import { useAppStore } from '../../store/useAppStore';

export const AccessDeniedPage: React.FC = () => {
  const currentUser = useAppStore((s) => s.currentUser);

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100dvh',
        padding: 24,
        textAlign: 'center',
        gap: 16,
      }}
    >
      <div style={{ fontSize: 64 }}>🔒</div>

      <h2
        style={{
          fontSize: 20,
          fontWeight: 700,
          color: 'var(--tg-theme-text-color, #000)',
          margin: 0,
        }}
      >
        Доступ закрыт
      </h2>

      <p
        style={{
          fontSize: 15,
          color: 'var(--tg-theme-hint-color, #999)',
          margin: 0,
          lineHeight: 1.5,
          maxWidth: 280,
        }}
      >
        Ваш аккаунт ожидает одобрения. Обратитесь к администратору киноклуба.
      </p>

      {currentUser && (
        <div
          style={{
            backgroundColor: 'var(--tg-theme-secondary-bg-color, #f1f1f1)',
            borderRadius: 10,
            padding: '12px 20px',
            marginTop: 8,
          }}
        >
          <div
            style={{
              fontSize: 12,
              color: 'var(--tg-theme-hint-color, #999)',
              marginBottom: 4,
            }}
          >
            Ваш Telegram ID
          </div>
          <div
            style={{
              fontSize: 20,
              fontWeight: 700,
              color: 'var(--tg-theme-text-color, #000)',
              fontFamily: 'monospace',
              letterSpacing: 1,
            }}
          >
            {currentUser.id}
          </div>
        </div>
      )}
    </div>
  );
};
