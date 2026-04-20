import type { StorybookConfig } from '@storybook/react-vite';

// Stories are colocated with their source in the consumer apps.
// See apps/storybook/README.md for rationale.
// [v84-1-5][ops:infra]
const config: StorybookConfig = {
  stories: [
    '../stories/**/*.mdx',
    '../../web/src/ui/**/*.stories.@(ts|tsx)',
    '../../api/src/templates/**/*.stories.@(ts|tsx)',
  ],
  addons: ['@storybook/addon-essentials'],
  framework: {
    name: '@storybook/react-vite',
    options: {},
  },
  // Serve brand/ at /brand/* so MDX pages can reference logos directly
  // (e.g. <img src="/brand/logos/logo.svg" />).
  staticDirs: [{ from: '../../../brand', to: '/brand' }],
  async viteFinal(config) {
    // Force the automatic JSX runtime for every .tsx file Vite sees, including
    // ones bind-mounted from apps/web/src/ui and apps/api/src/templates. Without
    // this, esbuild falls back to the classic transform on files outside the
    // storybook workspace root and throws "React is not defined" at runtime.
    config.esbuild = {
      ...config.esbuild,
      jsx: 'automatic',
    };
    return config;
  },
};

export default config;
