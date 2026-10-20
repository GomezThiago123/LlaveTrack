// Piezas chicas que se repiten en varias pantallas
import type { ReactNode } from 'react';
import { Link } from 'react-router';
import type { EstadoLlave } from '../api';
import { useSesion } from '../sesion';
import { TEXTO_ESTADO } from '../utiles';

export function Encabezado() {
  const { usuario, salir } = useSesion();
  return (
    <header className="encabezado">
      <Link to="/" className="marca">
        <img src="/llave.svg" alt="" width={28} height={28} />
        LlaveTrack
      </Link>
      {usuario && (
        <div className="encabezado-usuario">
          <span>{usuario.nombre}</span>
          <button type="button" className="boton-texto" onClick={salir}>
            Salir
          </button>
        </div>
      )}
    </header>
  );
}

export function Pagina({ children }: { children: ReactNode }) {
  return (
    <>
      <Encabezado />
      <main className="contenedor">{children}</main>
    </>
  );
}

export function EstadoEquipo({ online }: { online: boolean | null }) {
  if (online === null) return null;
  return (
    <p className={`equipo ${online ? 'equipo-online' : 'equipo-offline'}`}>
      <span className="punto" aria-hidden />
      {online ? 'Equipo en línea' : 'El equipo está desconectado: por ahora no entrega ni recibe llaves'}
    </p>
  );
}

export function ChipEstado({ estado }: { estado: EstadoLlave }) {
  return <span className={`chip chip-${estado.toLowerCase()}`}>{TEXTO_ESTADO[estado]}</span>;
}

export function Alerta({ tipo = 'error', children }: { tipo?: 'error' | 'aviso' | 'ok'; children: ReactNode }) {
  if (!children) return null;
  return (
    <p className={`alerta alerta-${tipo}`} role={tipo === 'error' ? 'alert' : 'status'}>
      {children}
    </p>
  );
}
