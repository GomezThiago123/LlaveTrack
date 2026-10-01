import express from 'express';

// La app se arma aparte de index.ts para poder testearla sin abrir un puerto.
export function crearApp() {
  const app = express();
  app.use(express.json());

  // Lo usa la web para saber si el servidor esta levantado.
  app.get('/api/salud', (_req, res) => {
    res.json({ ok: true });
  });

  return app;
}
