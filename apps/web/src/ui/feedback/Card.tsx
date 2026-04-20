// [v84-1-5][front-nextjs:ui]
'use client';

import type { HTMLAttributes, ReactNode } from 'react';

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  title?: string;
  children: ReactNode;
}

export function Card({ title, children, className = '', ...rest }: CardProps) {
  return (
    <div className={`rounded-lg border border-border bg-surface p-6 shadow-sm ${className}`} {...rest}>
      {title && <h3 className="mb-4 text-lg font-semibold text-text">{title}</h3>}
      {children}
    </div>
  );
}
