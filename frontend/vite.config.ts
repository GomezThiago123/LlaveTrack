import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  server: {
    // host: true para poder abrir la web desde el celular con la IP del notebook
    host: true,
    port: 5173,
    // En desarrollo, todo lo que empieza con /api se reenvia al servidor (evita CORS).
    // Tiene que coincidir con el PORT de backend/.env
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
});
