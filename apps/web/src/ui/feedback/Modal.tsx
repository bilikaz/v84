// [v84-1-5][front-nextjs:ui]
'use client';

import { useEffect, useRef, type ReactNode } from 'react';
import { Button } from '../primitives/Button';

export interface ModalProps {
  open: boolean;
  title: string;
  children: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  confirmVariant?: 'primary' | 'secondary' | 'danger';
  onConfirm: () => void;
  onCancel: () => void;
  loading?: boolean;
}

export function Modal({
  open,
  title,
  children,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  confirmVariant = 'primary',
  onConfirm,
  onCancel,
  loading = false,
}: ModalProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      dialog.showModal();
    } else if (!open && dialog.open) {
      dialog.close();
    }
  }, [open]);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    const handler = (e: Event) => {
      e.preventDefault();
      onCancel();
    };
    dialog.addEventListener('cancel', handler);
    return () => dialog.removeEventListener('cancel', handler);
  }, [onCancel]);

  if (!open) return null;

  return (
    <dialog
      ref={dialogRef}
      className="fixed inset-0 z-50 m-auto max-w-md rounded-lg border border-border bg-surface p-0 shadow-xl backdrop:bg-black/50"
      aria-labelledby="modal-title"
    >
      <div className="p-6">
        <h2 id="modal-title" className="text-lg font-semibold text-text">
          {title}
        </h2>
        <div className="mt-2 text-sm text-textMuted">{children}</div>
        <div className="mt-6 flex justify-end gap-3">
          <Button variant="secondary" onClick={onCancel} disabled={loading}>
            {cancelLabel}
          </Button>
          <Button
            variant={confirmVariant}
            onClick={onConfirm}
            disabled={loading}
          >
            {loading ? 'Processing...' : confirmLabel}
          </Button>
        </div>
      </div>
    </dialog>
  );
}
