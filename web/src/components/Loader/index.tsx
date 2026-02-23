import React from 'react';

interface LoaderProps {
  size?: number;
  center?: boolean;
}

export const Loader: React.FC<LoaderProps> = ({ size = 32, center = false }) => {
  const wrapper: React.CSSProperties = center
    ? { display: 'flex', justifyContent: 'center', alignItems: 'center', padding: '32px 0' }
    : { display: 'inline-flex' };

  return (
    <div style={wrapper}>
      <svg
        width={size}
        height={size}
        viewBox="0 0 24 24"
        fill="none"
        style={{ animation: 'spin 0.8s linear infinite' }}
      >
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        <circle
          cx="12"
          cy="12"
          r="10"
          stroke="var(--tg-theme-button-color, #2481cc)"
          strokeWidth="2.5"
          strokeDasharray="50"
          strokeDashoffset="15"
          strokeLinecap="round"
        />
      </svg>
    </div>
  );
};
