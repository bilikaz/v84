// [v84-1-5][front-nextjs:ui]
'use client';

import { type ButtonHTMLAttributes, forwardRef } from 'react';

export type ButtonVariant = 'primary' | 'secondary' | 'danger';
export type ButtonSize = 'sm' | 'md' | 'lg';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

const variantStyles: Record<ButtonVariant, string> = {
  primary:
    'bg-brand text-textInverse hover:bg-brandHover focus-visible:ring-brand',
  secondary:
    'bg-surfaceMuted text-text hover:bg-border focus-visible:ring-text border border-border',
  danger:
    'bg-danger text-textInverse hover:bg-accentHover focus-visible:ring-danger',
};

const sizeStyles: Record<ButtonSize, string> = {
  sm: 'px-2.5 py-1 text-xs rounded',
  md: 'px-4 py-2 text-sm rounded-md',
  lg: 'px-6 py-3 text-base rounded-md',
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'primary', size = 'md', className = '', disabled, children, ...rest }, ref) => {
    return (
      <button
        ref={ref}
        disabled={disabled}
        className={`inline-flex items-center justify-center font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 ${sizeStyles[size]} ${variantStyles[variant]} ${className}`}
        {...rest}
      >
        {children}
      </button>
    );
  },
);

Button.displayName = 'Button';
