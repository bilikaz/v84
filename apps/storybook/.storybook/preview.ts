import type { Preview } from '@storybook/react';
import '../../web/src/ui/styles.css';

// [v84-1-5][ops:infra]
const preview: Preview = {
  parameters: {
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },
  },
};

export default preview;
