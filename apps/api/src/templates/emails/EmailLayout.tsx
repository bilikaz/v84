import {
  Body,
  Container,
  Head,
  Html,
  Preview,
  Section,
  Text,
} from '@react-email/components';
import type { ReactNode } from 'react';
import { colors, radii, spacing, typography } from './theme';

export interface EmailLayoutProps {
  preview: string;
  children: ReactNode;
  appName: string;
  footerText?: string;
}

// [v84-1-6][back-nestjs:notifications]
export function EmailLayout({
  preview,
  children,
  appName,
  footerText,
}: EmailLayoutProps) {
  return (
    <Html>
      <Head />
      <Preview>{preview}</Preview>
      <Body style={body}>
        <Container style={container}>
          <Section style={header}>
            <Text style={brandMark}>{appName}</Text>
          </Section>
          <Section style={content}>{children}</Section>
          <Section style={footer}>
            <Text style={footerTextStyle}>{footerText ?? appName}</Text>
          </Section>
        </Container>
      </Body>
    </Html>
  );
}

const body: React.CSSProperties = {
  backgroundColor: colors.surfaceMuted,
  fontFamily: typography.fontFamily.sans,
  margin: 0,
  padding: 0,
};

const container: React.CSSProperties = {
  backgroundColor: colors.surface,
  maxWidth: '560px',
  margin: '40px auto',
  borderRadius: radii.lg,
  overflow: 'hidden',
  boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
};

const header: React.CSSProperties = {
  padding: `${spacing.lg} ${spacing.xl}`,
  borderBottom: `1px solid ${colors.border}`,
};

const brandMark: React.CSSProperties = {
  fontSize: typography.fontSize.lg,
  fontWeight: typography.fontWeight.bold,
  color: colors.brand,
  margin: 0,
};

const content: React.CSSProperties = {
  padding: spacing.xl,
};

const footer: React.CSSProperties = {
  padding: `${spacing.lg} ${spacing.xl}`,
  borderTop: `1px solid ${colors.border}`,
};

const footerTextStyle: React.CSSProperties = {
  fontSize: typography.fontSize.xs,
  color: colors.textSubtle,
  margin: 0,
};
