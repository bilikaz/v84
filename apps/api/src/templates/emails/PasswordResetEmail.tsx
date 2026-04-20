// [v84-3-2-1][back-nestjs:notifications]
import { Button, Heading, Link, Text } from '@react-email/components';
import { EmailLayout } from './EmailLayout';
import { colors, radii, spacing, typography } from './theme';

export interface PasswordResetEmailProps {
  appName: string;
  resetLink: string;
  expiresInMinutes: number;
}

export function PasswordResetEmail({
  appName,
  resetLink,
  expiresInMinutes,
}: PasswordResetEmailProps) {
  return (
    <EmailLayout appName={appName} preview={`Reset your ${appName} password`}>
      <Heading style={heading}>Reset your password</Heading>
      <Text style={paragraph}>
        We received a request to reset your password. Click the button below to choose a
        new one. This link expires in {expiresInMinutes} minutes.
      </Text>
      <Button href={resetLink} style={button}>
        Reset password
      </Button>
      <Text style={paragraph}>
        Or copy and paste this URL into your browser:{' '}
        <Link href={resetLink} style={link}>
          {resetLink}
        </Link>
      </Text>
      <Text style={subtle}>
        If you didn&apos;t request a password reset, you can safely ignore this email.
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
