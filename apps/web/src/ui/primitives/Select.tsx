// [v84-1-5][front-nextjs:ui]
'use client';

import { type SelectHTMLAttributes, forwardRef, useId } from 'react';

export interface SelectOption {
  value: string;
  label: string;
}

export interface SelectProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, 'id'> {
  label: string;
  error?: string;
  options: SelectOption[];
  placeholder?: string;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ label, error, options, placeholder, className = '', ...rest }, ref) => {
    const autoId = useId();
    const errorId = `${autoId}-error`;

    const baseClasses =
      'block w-full rounded-md border px-3 py-2 text-sm shadow-sm transition-colors focus:outline-none focus:ring-2 focus:ring-brand focus:border-brand disabled:bg-surfaceMuted disabled:text-textMuted';
    const errorClasses = error
      ? 'border-danger focus:ring-danger focus:border-danger'
      : 'border-border';

    return (
      <div className={`flex flex-col gap-1 ${className}`}>
        <label htmlFor={autoId} className="text-sm font-medium text-text">
          {label}
          {rest.required && (
            <span className="ml-1 text-danger" aria-hidden="true">*</span>
          )}
        </label>
        <select
          ref={ref}
          id={autoId}
          aria-describedby={error ? errorId : undefined}
          aria-invalid={error ? true : undefined}
          className={`${baseClasses} ${errorClasses}`}
          {...rest}
        >
          {placeholder && <option value="">{placeholder}</option>}
          {options.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
        {error && (
          <p id={errorId} className="text-sm text-danger" role="alert">{error}</p>
        )}
      </div>
    );
  },
);

Select.displayName = 'Select';
