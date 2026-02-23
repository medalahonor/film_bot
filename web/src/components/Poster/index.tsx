import React, { useState } from 'react';

interface PosterProps {
  src: string | null;
  alt: string;
  width?: number;
  height?: number;
  borderRadius?: number;
}

export const Poster: React.FC<PosterProps> = ({
  src,
  alt,
  width = 60,
  height = 90,
  borderRadius = 6,
}) => {
  const [failed, setFailed] = useState(false);

  const style: React.CSSProperties = {
    width,
    height,
    borderRadius,
    objectFit: 'cover',
    flexShrink: 0,
    backgroundColor: 'var(--tg-theme-secondary-bg-color, #f1f1f1)',
  };

  if (!src || failed) {
    return (
      <div
        style={{
          ...style,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: width > 80 ? 40 : 24,
        }}
      >
        🎬
      </div>
    );
  }

  return (
    <img
      src={src}
      alt={alt}
      style={style}
      onError={() => setFailed(true)}
      loading="lazy"
    />
  );
};
