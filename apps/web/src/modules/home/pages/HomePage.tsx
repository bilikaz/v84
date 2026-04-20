import Link from 'next/link';
import { copy } from '@/config';

// [v84-1-4][front-nextjs:pages]
export function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-4 text-center">
      <img
        src="/brand/logo.svg"
        alt={copy.appName}
        className="mb-8 h-32 w-32 sm:h-40 sm:w-40"
      />
      <h1 className="text-4xl font-bold tracking-tight sm:text-6xl">
        Welcome
      </h1>
      <p className="mt-4 max-w-xl text-lg text-gray-600 sm:text-xl">
        A modern platform for managing your workspace. Get started by creating
        an account or signing in.
      </p>
      <div className="mt-8 flex flex-col gap-4 sm:flex-row">
        <Link
          href="/auth/login"
          className="rounded-lg bg-brand px-6 py-3 text-sm font-semibold text-white shadow hover:bg-brandHover focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
        >
          Login
        </Link>
        <Link
          href="/auth/register"
          className="rounded-lg border border-gray-300 bg-white px-6 py-3 text-sm font-semibold text-gray-900 shadow-sm hover:bg-gray-50"
        >
          Register
        </Link>
      </div>
    </main>
  );
}
