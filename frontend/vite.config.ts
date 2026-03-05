import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import topLevelAwait from 'vite-plugin-top-level-await';

export default defineConfig({
  base: '/clpr/',
  plugins: [react()],
  optimizeDeps: {
    exclude: ['sqlite-wasm-http'],
  },
  worker: {
    format: 'es',
    plugins: () => [topLevelAwait()],
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
    rollupOptions: {
      output: {
        format: 'es',
      },
    },
  },
  server: {
    port: 5173,
  },
  define: {
    'import.meta.env.VITE_USE_TEST_DB': JSON.stringify(process.env.VITE_USE_TEST_DB === 'true'),
  },
});