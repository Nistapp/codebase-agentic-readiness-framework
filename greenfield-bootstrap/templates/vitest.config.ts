import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    globals: true,
    environment: 'node',
    // A freshly scaffolded project has no tests. Remove this with your first real test:
    // a gate that silently passes zero tests is worse than one that fails loudly.
    passWithNoTests: true,
    include: ['src/**/*.test.ts', 'test/**/*.test.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'text-summary', 'lcov', 'html'],
      include: ['src/**/*.ts'],
      exclude: [
        'src/**/*.test.ts',
        'src/agents/**',
        'src/**/index.ts',
      ],
      // Coverage thresholds are turned on with the first real test — 80/75/80/80 is
      // unreachable for an empty suite and would fail CI at commit #1.
      // thresholds: {
      //   statements: 80,
      //   branches: 75,
      //   functions: 80,
      //   lines: 80,
      // },
    },
  },
});
