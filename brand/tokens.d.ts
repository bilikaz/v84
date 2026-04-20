// [v84-1-6][front-nextjs-ui]
// Type declarations for brand/tokens.js.
// Keep in sync with tokens.js — both files are small and rarely change.

export declare const colors: {
  readonly brand: '#000000';
  readonly brandHover: '#1f2937';
  readonly accent: '#dc2626';
  readonly accentHover: '#b91c1c';
  readonly text: '#111111';
  readonly textMuted: '#6b7280';
  readonly textSubtle: '#9ca3af';
  readonly textInverse: '#ffffff';
  readonly surface: '#ffffff';
  readonly surfaceMuted: '#f6f6f6';
  readonly surfaceDark: '#111111';
  readonly border: '#eaeaea';
  readonly borderStrong: '#111111';
  readonly success: '#16a34a';
  readonly warning: '#d97706';
  readonly danger: '#dc2626';
};

export declare const radii: {
  readonly sm: '4px';
  readonly md: '6px';
  readonly lg: '8px';
  readonly xl: '12px';
  readonly full: '9999px';
};

export declare const spacing: {
  readonly xs: '4px';
  readonly sm: '8px';
  readonly md: '16px';
  readonly lg: '24px';
  readonly xl: '32px';
  readonly '2xl': '48px';
};

export declare const typography: {
  readonly fontFamily: {
    readonly sans: string;
    readonly display: string;
  };
  readonly fontSize: {
    readonly xs: '12px';
    readonly sm: '14px';
    readonly base: '15px';
    readonly lg: '18px';
    readonly xl: '22px';
    readonly '2xl': '28px';
    readonly '3xl': '36px';
  };
  readonly fontWeight: {
    readonly regular: 400;
    readonly medium: 500;
    readonly semibold: 600;
    readonly bold: 700;
  };
  readonly lineHeight: {
    readonly tight: 1.2;
    readonly base: 1.5;
    readonly relaxed: 1.75;
  };
};

export type Colors = typeof colors;
export type Radii = typeof radii;
export type Spacing = typeof spacing;
export type Typography = typeof typography;
