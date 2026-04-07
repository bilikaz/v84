# Suggestion: Vitest

## When

Every frontend (Next.js) project.

## Rule

Always suggest Vitest for frontend unit and component tests. Never suggest Jest for frontend — Vitest is Vite-native and faster.

## Why

Native TypeScript support (no ts-jest), Vite-native with instant feedback, Jest-compatible API (`describe/it/expect`), hot-reload during test dev.