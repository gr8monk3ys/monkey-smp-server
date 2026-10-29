/** @type {import('next').NextConfig} */
import createMDX from '@next/mdx';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const nextConfig = {
  // A static site: `next build` writes plain HTML, CSS and JS to out/, and Vercel serves that. Nothing runs on
  // a server, so there are no functions to pay for and every page reads fully without JavaScript.
  output: 'export',
  outputFileTracingRoot: __dirname,
  pageExtensions: ['js', 'jsx', 'mdx', 'ts', 'tsx'],
  poweredByHeader: false,
  reactStrictMode: true,
};

const withMDX = createMDX({});

export default withMDX(nextConfig);
