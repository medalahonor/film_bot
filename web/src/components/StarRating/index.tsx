import React from 'react';

interface StarRatingProps {
  value: number | null;
  onChange?: (rating: number) => void;
  readonly?: boolean;
  size?: 'sm' | 'md' | 'lg';
}

const MOODS: Record<number, string> = {
  1: 'Хуже некуда',
  2: 'Ужасно',
  3: 'Плохо',
  4: 'Слабо',
  5: 'Средне',
  6: 'Выше среднего',
  7: 'Хорошо',
  8: 'Отлично',
  9: 'Великолепно',
  10: 'Шедевр',
};

const ratingColor = (n: number): string => {
  if (n <= 4) return '#e74c3c';
  if (n <= 6) return '#95a5a6';
  if (n <= 9) return '#27ae60';
  return '#f39c12'; // 10 — золотой
};

export const StarRating: React.FC<StarRatingProps> = ({
  value,
  onChange,
  readonly = false,
  size = 'md',
}) => {
  const [hovered, setHovered] = React.useState<number | null>(null);

  const starSize = size === 'sm' ? 24 : size === 'lg' ? 40 : 32;
  const active = hovered ?? value;
  const color = active ? ratingColor(active) : 'var(--tg-theme-hint-color, #ccc)';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
      {/* Stars row */}
      <div style={{ display: 'flex', gap: 4 }}>
        {Array.from({ length: 10 }, (_, i) => i + 1).map((n) => {
          const filled = active !== null && n <= active;
          const starColor = filled ? ratingColor(n) : 'var(--tg-theme-hint-color, #aaa)';
          return (
            <button
              key={n}
              disabled={readonly}
              onMouseEnter={() => !readonly && setHovered(n)}
              onMouseLeave={() => !readonly && setHovered(null)}
              onClick={() => !readonly && onChange?.(n)}
              style={{
                background: 'none',
                border: 'none',
                cursor: readonly ? 'default' : 'pointer',
                padding: 2,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: 2,
              }}
            >
              <span style={{ fontSize: starSize, lineHeight: 1, color: starColor, transition: 'color 0.1s' }}>
                ★
              </span>
              <span style={{ fontSize: 10, lineHeight: 1, color: starColor, transition: 'color 0.1s' }}>
                {n}
              </span>
            </button>
          );
        })}
      </div>

      {/* Mood label */}
      <div
        style={{
          minHeight: 20,
          fontSize: size === 'sm' ? 12 : 14,
          fontWeight: 600,
          color,
          transition: 'color 0.15s',
        }}
      >
        {active ? MOODS[active] : (readonly ? '—' : 'Выберите оценку')}
      </div>
    </div>
  );
};
