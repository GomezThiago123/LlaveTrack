// Piezas chicas que se repiten en varias pantallas
import type { ReactNode } from 'react';
import { NavLink } from 'react-router';
import {
  ClipboardList,
  Cpu,
  History,
  KeyRound,
  LayoutGrid,
  UserRound,
  Users,
  type LucideIcon,
} from 'lucide-react';
import type { EstadoLlave } from '../api';
import { useSesion } from '../sesion';
import { esPreceptor, TEXTO_ESTADO, TEXTO_ROL } from '../utiles';

interface ItemNav {
  a: string;
  texto: string;
  Icono: LucideIcon;
}

// Docente: aulas, sus llaves (US-17) y su cuenta.
// Preceptor y admin: ademas, faltantes, historial (US-12/13), equipo y docentes (US-09).
const NAV_DOCENTE: ItemNav[] = [
  { a: '/aulas', texto: 'Aulas', Icono: LayoutGrid },
  { a: '/mis-llaves', texto: 'Mis llaves', Icono: KeyRound },
  { a: '/cuenta', texto: 'Cuenta', Icono: UserRound },
];
const NAV_PRECEPTOR: ItemNav[] = [
  { a: '/aulas', texto: 'Aulas', Icono: LayoutGrid },
  { a: '/faltantes', texto: 'Faltantes', Icono: ClipboardList },
  { a: '/historial', texto: 'Historial', Icono: History },
  { a: '/equipo', texto: 'Equipo', Icono: Cpu },
  { a: '/docentes', texto: 'Docentes', Icono: Users },
];

/** Pantalla con login: franja azul arriba, contenido y barra de navegacion abajo. */
export function PaginaApp({ titulo, derecha, children }: { titulo: string; derecha?: ReactNode; children: ReactNode }) {
  const { usuario } = useSesion();
  const preceptor = usuario ? esPreceptor(usuario.rol) : false;
  const items = preceptor ? NAV_PRECEPTOR : NAV_DOCENTE;

  return (
    <>
      <header className="encabezado">
        <div className="encabezado-contenido">
          <div>
            <h1>{titulo}</h1>
            {usuario && <span className="rol">{TEXTO_ROL[usuario.rol]}</span>}
          </div>
          <div className="encabezado-derecha">
            {derecha}
            {/* El preceptor no tiene "Cuenta" en la barra de abajo (no entra): va arriba */}
            {preceptor && (
              <NavLink to="/cuenta" className="boton-icono" aria-label="Mi cuenta">
                <UserRound size={18} />
              </NavLink>
            )}
          </div>
        </div>
      </header>
      <main className="contenedor">{children}</main>
      <nav className="barra-inferior" aria-label="Navegación principal">
        <ul>
          {items.map(({ a, texto, Icono }) => (
            <li key={a}>
              <NavLink to={a} className={({ isActive }) => (isActive ? 'activo' : '')}>
                <Icono size={20} aria-hidden />
                {texto}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
    </>
  );
}

/** Pantalla sin login (login, recuperar, vista publica): portada azul y contenido. */
export function PaginaSimple({ subtitulo, children }: { subtitulo?: string; children: ReactNode }) {
  return (
    <>
      <header className="portada">
        <span className="logo" aria-hidden>
          <KeyRound size={30} />
        </span>
        <h1>LlaveTrack</h1>
        <p>{subtitulo ?? 'Control de llaves de las aulas'}</p>
        <span className="etiqueta">ETEC · UBA</span>
      </header>
      <main className="contenedor">{children}</main>
    </>
  );
}

/** Si el equipo esta conectado (US-22). null = todavia no se sabe. */
export function PildoraEquipo({ online }: { online: boolean | null }) {
  if (online === null) return null;
  return (
    <span className={`pildora ${online ? 'pildora-online' : 'pildora-offline'}`}>
      <span className="punto" aria-hidden />
      {online ? 'Equipo en línea' : 'Equipo desconectado'}
    </span>
  );
}

export function Insignia({ estado }: { estado: EstadoLlave }) {
  return <span className={`insignia insignia-${estado.toLowerCase()}`}>{TEXTO_ESTADO[estado]}</span>;
}

export function Alerta({ tipo = 'error', children }: { tipo?: 'error' | 'aviso' | 'ok'; children: ReactNode }) {
  if (!children) return null;
  return (
    <p className={`alerta alerta-${tipo}`} role={tipo === 'error' ? 'alert' : 'status'}>
      {children}
    </p>
  );
}

export function EtiquetaSeccion({ children, derecha }: { children: ReactNode; derecha?: ReactNode }) {
  return (
    <h2 className="etiqueta-seccion">
      <span>{children}</span>
      {derecha && <span>{derecha}</span>}
    </h2>
  );
}

/** Botones de opcion unica, ej. Todas · Peine 1 · Peine 2 */
export function Segmentado<T extends string>({
  valor,
  opciones,
  alCambiar,
  etiqueta,
}: {
  valor: T;
  opciones: { valor: T; texto: ReactNode }[];
  alCambiar: (valor: T) => void;
  etiqueta: string;
}) {
  return (
    <div className="segmentado" role="radiogroup" aria-label={etiqueta}>
      {opciones.map((o) => (
        <button key={o.valor} type="button" role="radio" aria-checked={o.valor === valor} onClick={() => alCambiar(o.valor)}>
          {o.texto}
        </button>
      ))}
    </div>
  );
}

export function Interruptor({
  activo,
  alCambiar,
  etiqueta,
  deshabilitado = false,
}: {
  activo: boolean;
  alCambiar: (activo: boolean) => void;
  etiqueta: string;
  deshabilitado?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      className="interruptor"
      aria-checked={activo}
      aria-label={etiqueta}
      disabled={deshabilitado}
      onClick={() => alCambiar(!activo)}
    />
  );
}
