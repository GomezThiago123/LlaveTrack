import { useEffect, useState } from 'react';

type EstadoServidor = 'verificando' | 'conectado' | 'sin conexion';

export default function App() {
  const [servidor, setServidor] = useState<EstadoServidor>('verificando');

  // Al abrir la pagina, pregunta al servidor si esta levantado
  useEffect(() => {
    fetch('/api/salud')
      .then((res) => setServidor(res.ok ? 'conectado' : 'sin conexion'))
      .catch(() => setServidor('sin conexion'));
  }, []);

  return (
    <main className="contenedor">
      <h1>LlaveTrack</h1>
      <p>Llaves de las aulas de la ETEC-UBA</p>
      <p className={`estado estado-${servidor.replace(' ', '-')}`}>
        Servidor: {servidor}
      </p>
    </main>
  );
}
