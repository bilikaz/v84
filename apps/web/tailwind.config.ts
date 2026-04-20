// [v84-1-4][front-nextjs:ui]
import type { Config } from 'tailwindcss';
import { colors, radii, spacing, typography } from '../../brand/tokens';

// Tailwind's fontWeight/lineHeight types want Record<string, string>,
// but the brand tokens expose them as numbers so React.CSSProperties is happy.
// Stringify at the Tailwind boundary.
const stringify = (o: Record<string, string | number>): Record<string, string> =>
  Object.fromEntries(Object.entries(o).map(([k, v]) => [k, String(v)]));

const config: Config = {
  content: [
    './src/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors,
      borderRadius: radii,
      spacing,
      fontFamily: typography.fontFamily,
      fontSize: typography.fontSize,
      fontWeight: stringify(typography.fontWeight),
      lineHeight: stringify(typography.lineHeight),
    },
  },
  plugins: [],
};

export default config;
