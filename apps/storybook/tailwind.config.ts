// [v84-1-5][front-nextjs:ui]
import type { Config } from 'tailwindcss';
import { colors, radii, spacing, typography } from '../../brand/tokens';

// See apps/web/tailwind.config.ts for why we stringify these two.
const stringify = (o: Record<string, string | number>): Record<string, string> =>
  Object.fromEntries(Object.entries(o).map(([k, v]) => [k, String(v)]));

const config: Config = {
  content: [
    '../web/src/ui/**/*.{ts,tsx}',
    '../api/src/templates/**/*.{ts,tsx}',
    './stories/**/*.{ts,tsx,mdx}',
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
