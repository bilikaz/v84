// [v84-1-6][front-nextjs:ui]
// V84 brand tokens — CommonJS version for node runtime (api email templates).
// Keep the values in this file in sync with the sibling tokens.mjs.
// See brand/README.md for the "source vs view" pattern and why we ship dual format.

'use strict';

exports.colors = {
  // Primary brand palette — black / red / white.
  brand: '#000000',        // V84 black — primary identity, used for the "V"
  brandHover: '#1f2937',   // slight lift on black for hover/pressed states
  accent: '#dc2626',       // V84 red — used for the "8" and accent fills
  accentHover: '#b91c1c',  // hover on red

  text: '#111111',
  textMuted: '#6b7280',
  textSubtle: '#9ca3af',
  textInverse: '#ffffff',  // text on black surfaces

  surface: '#ffffff',      // V84 white — used for the "4" fill and page bg
  surfaceMuted: '#f6f6f6',
  surfaceDark: '#111111',  // dark surface for reversed contexts
  border: '#eaeaea',
  borderStrong: '#111111', // strong border used as letterform stroke

  success: '#16a34a',
  warning: '#d97706',
  danger: '#dc2626',
};

exports.radii = {
  sm: '4px',
  md: '6px',
  lg: '8px',
  xl: '12px',
  full: '9999px',
};

exports.spacing = {
  xs: '4px',
  sm: '8px',
  md: '16px',
  lg: '24px',
  xl: '32px',
  '2xl': '48px',
};

exports.typography = {
  fontFamily: {
    sans: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    display: 'var(--font-display), system-ui, sans-serif',
  },
  fontSize: {
    xs: '12px',
    sm: '14px',
    base: '15px',
    lg: '18px',
    xl: '22px',
    '2xl': '28px',
    '3xl': '36px',
  },
  fontWeight: {
    regular: 400,
    medium: 500,
    semibold: 600,
    bold: 700,
  },
  lineHeight: {
    tight: 1.2,
    base: 1.5,
    relaxed: 1.75,
  },
};
