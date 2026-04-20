// [v84-3-1-2][back-nestjs:notifications]
import { Button, Heading, Link, Text } from '@react-email/components';
import { EmailLayout } from './EmailLayout';
import { colors, radii, spacing, typography } from './theme';

export interface VerificationEmailProps {
  appName: string;
  verifyLink: string;
  expiresInMinutes: number;
}

export function VerificationEmail({ appName, verifyLink, expiresInMinutes }: VerificationEmailProps) {
  return (
    <EmailLayout appName={appName} preview={`Verify your email to finish creating your ${appName} account`}>
      <Heading style={heading}>Verify your email</Heading>
      <Text style={paragraph}>
        Welcome to {appName}. Click the button below to confirm this email and finish creating
        your account. The link expires in {expiresInMinutes} minutes.
      </Text>
      <Button href={verifyLink} style={button}>
        Verify email
      </Button>
      <Text style={paragraph}>
        Or copy and paste this URL into your browser:{' '}
        <Link href={verifyLink} style={link}>
          {verifyLink}
        </Link>
      </Text>
      <Text style={subtle}>
        If you didn&apos;t try to sign up, you can safely ignore this email — no account
        will be created.
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
