import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    host: '0.0.0.0', // Allow LAN access
    port: 3001,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        // Ensure cookies and credentials are passed correctly
        cookieDomainRewrite: '', // Keep original domain
        // Ensure WebSocket and HTTP requests are proxied correctly
        ws: true,
      },
    },
  },
  build: {
    sourcemap: true, // Enable source maps for production builds
  },
  optimizeDeps: {
    // Disable source maps for pre-bundled dependencies to avoid warnings
    esbuildOptions: {
      sourcemap: false,
    },
  },
});












