import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
  server: {
    port: 9090,
    host: '0.0.0.0', // Permite acesso via Docker Nginx e rede local
    strictPort: true,
    proxy: {
      '/identity': 'http://localhost:8000',
      '/inventory': 'http://localhost:8000',
      '/purchasing': 'http://localhost:8000',
      '/crm': 'http://localhost:8000',
      '/sales': 'http://localhost:8000',
      '/billing': 'http://localhost:8000',
      '/finance': 'http://localhost:8000',
      '/docs': 'http://localhost:8000',
      '/openapi.json': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    },
  },
});
