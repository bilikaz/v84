# Suggestion: Playwright

## When

Projects with end-to-end user flows spanning multiple pages, or when the vibe coder explicitly mentions "I need this to work end-to-end."

## Rule

Suggest Playwright only for e2e testing — not for unit or component tests. Pairs with Jest (backend) and Vitest (frontend) which handle the lower-level tests.

## Why

Only tool that tests frontend → API → DB in one real browser pass. Tracing, screenshots, and video on failure. Heavy and slow compared to unit tests — include only when full-stack verification is needed.