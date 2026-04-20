// Tests run inside the test stack's API container (docker/test/docker-compose.yml),
// which has its own DB, Redis, and Mailpit — fully isolated from dev.
// All env vars are already set by the compose environment block.
// We only set NODE_ENV here so test-specific behavior (if any) activates.

// [v84-1-3][ops:testing]
process.env.NODE_ENV = 'test';
