// [v84-2-1-3][ops:testing]
// Minimal faker stub for jest (faker 10 is ESM-only, jest is CJS).
// Returns deterministic unique values — factories use these as defaults
// which tests always override with explicit fixtures.

let counter = 0;
const nextId = () => ++counter;

export const faker = {
  internet: {
    username: () => `stub-user-${nextId()}`,
    email: () => `stub-${nextId()}@example.test`,
  },
  string: {
    uuid: () => '00000000-0000-7000-8000-000000000000',
  },
};
