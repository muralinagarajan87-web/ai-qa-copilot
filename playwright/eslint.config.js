import js from '@eslint/js';
import tseslint from '@typescript-eslint/eslint-plugin';
import tsparser from '@typescript-eslint/parser';
import playwright from 'eslint-plugin-playwright';
import globals from 'globals';

export default [
  js.configs.recommended,
  {
    files: ['**/*.ts'],
    languageOptions: {
      parser: tsparser,
      parserOptions: { ecmaVersion: 2022, sourceType: 'module' },
      globals: globals.node,
    },
    plugins: {
      '@typescript-eslint': tseslint,
      playwright,
    },
    rules: {
      ...playwright.configs['flat/recommended'].rules,
      // These two are the hard project standards (see docs/architecture/design.md
      // "Playwright Standards") -- enforced mechanically, not just by prompt.
      'playwright/no-wait-for-timeout': 'error',
      'playwright/no-element-handle': 'error',
      'playwright/no-networkidle': 'warn',
      'playwright/no-nth-methods': 'warn',
      // Assertions are often delegated to Page Object helper methods (POM
      // pattern) instead of a bare `expect()` in the spec file -- without
      // this, the rule can't see into `page.expectFoo()` and false-flags
      // every such test as having no assertions.
      'playwright/expect-expect': ['error', { assertFunctionPatterns: ['^expect[A-Z]'] }],
    },
  },
];
