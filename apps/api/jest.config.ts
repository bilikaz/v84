import type { Config } from 'jest';

// [v84-1-3][ops:testing]
const config: Config = {
  moduleFileExtensions: ['js', 'json', 'ts'],
  rootDir: 'src',
  testRegex: '.*\\.spec\\.ts$',
  transform: {
    '^.+\\.ts$': 'ts-jest',
  },
  collectCoverageFrom: ['**/*.ts', '!**/node_modules/**', '!**/dist/**'],
  coverageDirectory: '../coverage',
  testEnvironment: 'node',
};

export default config;
