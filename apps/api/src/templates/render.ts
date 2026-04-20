import { render } from '@react-email/render';
import { createElement } from 'react';

export interface RenderedContent {
  html: string;
  text: string;
}

// Renders any React component to HTML + plain text. Not email-specific —
// works for any React template that needs to produce both formats.
// [v84-1-6][back-nestjs:api]
export async function renderToHtmlAndText<P>(
  Component: (props: P) => React.ReactElement,
  props: P,
): Promise<RenderedContent> {
  const element = createElement(Component as never, props as never);
  const [html, text] = await Promise.all([
    render(element),
    render(element, { plainText: true }),
  ]);
  return { html, text };
}
