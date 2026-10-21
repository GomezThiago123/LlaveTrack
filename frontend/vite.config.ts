import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// Este archivo lo ejecuta Node, que tiene `process`. El tsconfig es el de la web (sin los tipos
// de Node), asi que se declara aca lo unico que se usa.
declare const process: { env: Record<string, string | undefined> };

export default defineConfig({
  plugins: [react()],
  server: {
    // host: true para poder abrir la web desde el celular con la IP del notebook
    host: true,
    port: 5173,
    // En desarrollo, todo lo que empieza con /api se reenvia al servidor (evita CORS).
    // Tiene que coincidir con el PORT de backend/.env. Otro servidor: LLAVETRACK_API=http://localhost:8001
    proxy: {
      '/api': process.env.LLAVETRACK_API ?? 'http://localhost:8000',
    },
  },
});
