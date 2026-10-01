import 'dotenv/config';

// Toda la configuracion sale de variables de entorno (.env), con valores por defecto
// para desarrollo. Los tiempos y limites del sistema se van a agregar aca.
export const config = {
  port: Number(process.env.PORT ?? 3000),
};
