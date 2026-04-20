// [v84-1-5][front-nextjs:ui]
export type BadgeStatus = 'draft' | 'active' | 'drawn' | 'closed';

export interface BadgeProps {
  status: BadgeStatus;
  className?: string;
}

const statusStyles: Record<BadgeStatus, string> = {
  draft: 'bg-surfaceMuted text-textMuted border border-border',
  active: 'bg-success text-textInverse',
  drawn: 'bg-brand text-textInverse',
  closed: 'bg-danger text-textInverse',
};

export function Badge({ status, className = '' }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${statusStyles[status]} ${className}`}
    >
      {status}
    </span>
  );
}
