import type { Config } from 'jest';

// Integration tests boot the real AppModule against the real dev MariaDB + Redis + Mailpit
// inside the dev compose stack. Each suite gets an isolated schema (`local_test`) that is
// wiped between tests. Do not run against the dev DB — `test/env.ts` asserts the name.

// [v84-1-3][ops:testing]
const config: Config = {
  rootDir: '.',
  testMatch: ['<rootDir>/test/**/*.e2e.spec.ts'],
  moduleFileExtensions: ['ts', 'tsx', 'js', 'json'],
  transform: {
    '^.+\\.tsx?$': ['ts-jest', { tsconfig: '<rootDir>/test/tsconfig.json' }],
  },
  // faker 10 is ESM-only and can't be loaded by jest's CJS runtime. Since
  // factory-generated random fields are never asserted in tests (tests always
  // pass deterministic overrides), we stub faker with a lightweight mock.
  moduleNameMapper: {
    '^@faker-js/faker$': '<rootDir>/test/helpers/faker-stub.ts',
  },
  setupFiles: ['<rootDir>/test/env.ts'],
  testTimeout: 30_000,
  maxWorkers: 1, // one DB, one Redis — suites mutate shared state so serial is safest
};

export default config;
