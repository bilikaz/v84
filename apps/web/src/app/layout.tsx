// [v84-1-4][front-nextjs:pages]
import type { Metadata } from 'next';
import './globals.css';
import { AuthProvider, GoogleProvider } from '@/common/providers';
import { copy } from '@/config';

export const metadata: Metadata = {
  title: copy.appName,
  description: copy.appName,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50 text-gray-900 antialiased">
        <GoogleProvider>
          <AuthProvider>{children}</AuthProvider>
        </GoogleProvider>
      </body>
    </html>
  );
}
