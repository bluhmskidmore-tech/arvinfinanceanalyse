import tsParser from "@typescript-eslint/parser";
import tsPlugin from "@typescript-eslint/eslint-plugin";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";

// Runtime payloads belong in src/mocks. Keep exceptions tied to verified
// selectors and existing demo clients until their domains are migrated.
const mockImportEntryPoints = [
  "src/api/client.ts",
  "src/api/clientContext.ts",
  "src/api/candidateFinancialIndicatorsClient.ts",
  "src/api/homeMarketTickerClient.ts",
  "src/api/homeSupplementalClient.ts",
];
const mockImportMessage =
  "Runtime imports from src/mocks belong in data-source selectors, explicit demo entry points, or tests.";

export default [
  {
    ignores: ["dist", "coverage"],
  },
  {
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        ecmaVersion: "latest",
        sourceType: "module",
        ecmaFeatures: {
          jsx: true,
        },
      },
    },
    plugins: {
      "@typescript-eslint": tsPlugin,
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...tsPlugin.configs.recommended.rules,
      ...reactHooks.configs.recommended.rules,
      "@typescript-eslint/no-unused-vars": [
        "error",
        {
          argsIgnorePattern: "^_",
          varsIgnorePattern: "^_",
          caughtErrorsIgnorePattern: "^_",
        },
      ],
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
    },
  },
  {
    files: ["src/**/*.{ts,tsx}"],
    ignores: [
      "src/mocks/**",
      "src/test/**",
      "**/*.test.{ts,tsx}",
      ...mockImportEntryPoints,
    ],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [{
            group: ["**/mocks/**"],
            allowTypeImports: true,
            message: mockImportMessage,
          }],
        },
      ],
      "no-restricted-syntax": [
        "error",
        {
          selector: "ImportExpression[source.value=/mocks\\//]",
          message: mockImportMessage,
        },
      ],
    },
  },
];
