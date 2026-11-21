import { defineConfig } from 'vite'
import { axisPreview } from './scripts/axis-preview.ts'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import applicationVersion from '../../../versions/version.json' with { type: 'json' }

if (applicationVersion.schema_version !== 1 || !/^\d+\.\d+\.\d+\.\d+-(dev|release)$/.test(applicationVersion.version)) {
  throw new Error('Expected a four-part application version ending in -dev or -release')
}

export default defineConfig({
  base: './',
  define: {
    __ARCNOS_VERSION__: JSON.stringify(applicationVersion.version),
  },
  plugins: [axisPreview(), vue(), tailwindcss(), {
    name: 'desktop-content-policy',
    apply: 'build',
    transformIndexHtml: () => [{
      tag: 'meta',
      attrs: {
        'http-equiv': 'Content-Security-Policy',
        content: "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'none'; object-src 'none'; frame-src 'none'; base-uri 'none'; form-action 'none'",
      },
      injectTo: 'head',
    }],
  }],
  resolve: {
    alias: {
      '@': new URL('./src', import.meta.url).pathname,
    },
  },
})
