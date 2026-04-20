// [v84-1-5][front-nextjs:ui]
'use client';

import {
  type InputHTMLAttributes,
  type TextareaHTMLAttributes,
  forwardRef,
  useId,
} from 'react';

interface BaseInputProps {
  label: string;
  error?: string;
}

export interface TextInputProps
  extends BaseInputProps,
    Omit<InputHTMLAttributes<HTMLInputElement>, 'id'> {
  as?: 'input';
}

export interface TextareaProps
  extends BaseInputProps,
    Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, 'id'> {
  as: 'textarea';
}

export type InputProps = TextInputProps | TextareaProps;

export const Input = forwardRef<
  HTMLInputElement | HTMLTextAreaElement,
  InputProps
>((props, ref) => {
  const autoId = useId();
  const { label, error, as, className = '', required, ...rest } = props;
  const inputId = autoId;
  const errorId = `${inputId}-error`;

  const baseClasses =
    'block w-full rounded-md border px-3 py-2 text-sm shadow-sm transition-colors focus:outline-none focus:ring-2 focus:ring-brand focus:border-brand disabled:bg-surfaceMuted disabled:text-textMuted';
  const errorClasses = error
    ? 'border-danger focus:ring-danger focus:border-danger'
    : 'border-border';

  return (
    <div className={`flex flex-col gap-1 ${className}`}>
      <label htmlFor={inputId} className="text-sm font-medium text-text">
        {label}
        {required && (
          <span className="ml-1 text-danger" aria-hidden="true">
            *
          </span>
        )}
      </label>
      {as === 'textarea' ? (
        <textarea
          ref={ref as React.Ref<HTMLTextAreaElement>}
          id={inputId}
          required={required}
          aria-describedby={error ? errorId : undefined}
          aria-invalid={error ? true : undefined}
          className={`${baseClasses} ${errorClasses}`}
          {...(rest as TextareaHTMLAttributes<HTMLTextAreaElement>)}
        />
      ) : (
        <input
          ref={ref as React.Ref<HTMLInputElement>}
          id={inputId}
          required={required}
          aria-describedby={error ? errorId : undefined}
          aria-invalid={error ? true : undefined}
          className={`${baseClasses} ${errorClasses}`}
          {...(rest as InputHTMLAttributes<HTMLInputElement>)}
        />
      )}
      {error && (
        <p id={errorId} className="text-sm text-danger" role="alert">
          {error}
        </p>
      )}
    </div>
  );
});

Input.displayName = 'Input';
