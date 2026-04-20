// [v84-3-1-2][back-nestjs:notifications]
import { Button, Heading, Text } from '@react-email/components';
import { EmailLayout } from './EmailLayout';
import { colors, radii, spacing, typography } from './theme';

export interface WelcomeEmailProps {
  appName: string;
  username: string;
  dashboardLink: string;
}

export function WelcomeEmail({ appName, username, dashboardLink }: WelcomeEmailProps) {
  return (
    <EmailLayout appName={appName} preview={`Welcome to ${appName} — your account is ready`}>
      <Heading style={heading}>Welcome to {appName}, {username}</Heading>
      <Text style={paragraph}>
        Your account is ready. Sign in any time at the link below — and if you haven&apos;t
        yet, take a moment to enable two-factor authentication from your account settings.
      </Text>
      <Button href={dashboardLink} style={button}>
        Go to dashboard
      </Button>
      <Text style={subtle}>
        If you didn&apos;t create this account, please reply to let us know.
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

const subtle: React.CSSProperties = {
  fontSize: typography.fontSize.sm,
  lineHeight: typography.lineHeight.base,
  color: colors.textMuted,
  margin: `${spacing.lg} 0 0`,
};
