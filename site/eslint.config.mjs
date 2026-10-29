import { defineConfig, globalIgnores } from 'eslint/config';
import nextVitals from 'eslint-config-next/core-web-vitals';
import nextTs from 'eslint-config-next/typescript';

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  globalIgnores(['.next/**', 'out/**', 'build/**', 'next-env.d.ts', 'node_modules/**', 'public/**']),
  {
    rules: {
      // A static export can't optimize images at request time, and every picture already comes in the sizes
      // it needs (img/*-800.webp, *-1600.webp with srcset), so the pages use plain <img>.
      '@next/next/no-img-element': 'off',
      // Pages link to each other with plain <a>: each page has its own stylesheet (guide.css, changes.css),
      // and a full page load is what the static site always did.
      '@next/next/no-html-link-for-pages': 'off',
    },
  },
]);

export default eslintConfig;
