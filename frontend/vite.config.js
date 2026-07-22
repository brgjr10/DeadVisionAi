import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/tools': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/api/models/': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/v1': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
      '/upstream': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
      '/ui': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
      '/logs': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
      '/unload': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
      '/sdapi': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
    },
  },
});