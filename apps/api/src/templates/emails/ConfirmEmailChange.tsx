import { Button, Heading, Link, Text } from '@react-email/components';
import { EmailLayout } from './EmailLayout';
import { colors, radii, spacing, typography } from './theme';

export interface ConfirmEmailChangeProps {
  appName: string;
  confirmLink: string;
  newEmail: string;
  expiresInMinutes: number;
}

// [v84-4-2-2][back-nestjs:notifications]
export function ConfirmEmailChange({
  appName,
  confirmLink,
  newEmail,
  expiresInMinutes,
}: ConfirmEmailChangeProps) {
  return (
    <EmailLayout appName={appName} preview={`Confirm your new email address for ${appName}`}>
      <Heading style={heading}>Confirm your new email</Heading>
      <Text style={paragraph}>
        You requested to change your email address to <strong>{newEmail}</strong>.
        Click the button below to confirm. This link expires in {expiresInMinutes} minutes.
      </Text>
      <Button href={confirmLink} style={button}>
        Confirm email change
      </Button>
      <Text style={paragraph}>
        Or copy and paste this URL into your browser:{' '}
        <Link href={confirmLink} style={link}>
          {confirmLink}
        </Link>
      </Text>
      <Text style={subtle}>
        If you didn&apos;t request this change, you can safely ignore this email —
        your email address will not be changed.
      </Text>
    </EmailLayout>
  );
}

const heading: React.CSSProperties = {
  fontSize: typography.fontSize.xl,
  fontWeight: typography.fontWeight.semibold,
  color: colors.text,
  margin: `0 0 ${spacing.md}`,
};

const paragraph: React.CSSProperties = {
  fontSize: typography.fontSize.base,
  lineHeight: typography.lineHeight.base,
  color: colors.text,
  margin: `0 0 ${spacing.lg}`,
};

const button: React.CSSProperties = {
  backgroundColor: colors.brand,
  color: colors.surface,
  padding: `${spacing.sm} ${spacing.lg}`,
  borderRadius: radii.md,
  fontSize: typography.fontSize.base,
  fontWeight: typography.fontWeight.semibold,
  textDecoration: 'none',
  display: 'inline-block',
};

const link: React.CSSProperties = {
  color: colors.brand,
  wordBreak: 'break-all',
};

const subtle: React.CSSProperties = {
  fontSize: typography.fontSize.sm,
  lineHeight: typography.lineHeight.base,
  color: colors.textMuted,
  margin: `${spacing.lg} 0 0`,
};
