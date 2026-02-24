import React, { useState } from 'react';
import { useAppStore } from '../../store/useAppStore';

export const AccessDeniedPage: React.FC = () => {
  const currentUser = useAppStore((s) => s.currentUser);
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    if (!currentUser?.id) return;
    navigator.clipboard.writeText(String(currentUser.id)).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

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
        Ваш аккаунт ожидает одобрения. Передайте свой Telegram ID администратору киноклуба, чтобы получить доступ.
      </p>

      {currentUser && (
        <div
          style={{
            backgroundColor: 'var(--tg-theme-secondary-bg-color, #f1f1f1)',
            borderRadius: 10,
            padding: '12px 20px',
            marginTop: 8,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 10,
          }}
        >
          <div
            style={{
              fontSize: 12,
              color: 'var(--tg-theme-hint-color, #999)',
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
          <button
            onClick={handleCopy}
            style={{
              marginTop: 2,
              padding: '8px 20px',
              borderRadius: 8,
              border: 'none',
              backgroundColor: copied
                ? 'var(--tg-theme-hint-color, #999)'
                : 'var(--tg-theme-button-color, #007aff)',
              color: 'var(--tg-theme-button-text-color, #fff)',
              fontSize: 14,
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'background-color 0.2s',
            }}
          >
            {copied ? 'Скопировано!' : 'Скопировать ID'}
          </button>
        </div>
      )}
    </div>
  );
};
