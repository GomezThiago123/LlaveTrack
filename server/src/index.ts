import { crearApp } from './app.js';
import { config } from './config.js';

crearApp().listen(config.port, () => {
  console.log(`Servidor LlaveTrack escuchando en http://localhost:${config.port}`);
});
