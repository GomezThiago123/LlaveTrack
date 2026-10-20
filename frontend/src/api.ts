// Todo lo que la web le pide al servidor pasa por este archivo.
// Las rutas empiezan con /api: en desarrollo Vite las reenvia al backend (ver vite.config.ts).

export type Rol = 'DOCENTE' | 'PRECEPTOR' | 'ADMIN';
export type EstadoLlave = 'DISPONIBLE' | 'RESERVADA' | 'PRESTADA' | 'BAJA';
export type EstadoReserva = 'PENDIENTE' | 'USADA' | 'VENCIDA' | 'CANCELADA';

export interface Usuario {
  id: number;
  nombre: string;
  apellido: string;
  email: string;
  telefono: string | null;
  rol: Rol;
}

export interface EstadoPublico {
  equipoOnline: boolean;
  aulas: { id: number; nombre: string; estado: EstadoLlave }[];
}

export interface Aula {
  id: number;
  nombre: string;
  estado: EstadoLlave;
  // Quien tiene (o reservo) la llave, desde que hora y su telefono (US-02: lo ven todos)
  tenedor: { usuarioId: number; nombre: string; apellido: string; telefono: string | null; desde: string } | null;
}

export interface Reserva {
  id: number;
  aula: string;
  codigo: string;
  creadaEn: string; // fechas ISO en UTC
  expiraEn: string;
  estado: EstadoReserva;
}

export interface CuentaBloqueada {
  id: number;
  nombre: string;
  apellido: string;
  email: string;
  bloqueadoHasta: string; // fecha ISO en UTC
}

export interface Incidente {
  id: number;
  ocurridoEn: string; // fecha ISO en UTC
  tipo: string; // LLAVE_NO_ENCONTRADA, MOTOR_NO_GIRA, ...
  descripcion: string; // para mostrar: "Llave no encontrada"
  aula: string | null;
  docente: string | null;
  detalle: string | null;
}

export interface Prestamo {
  id: number;
  aula: string;
  docente: { id: number; nombre: string; apellido: string; email: string; telefono: string | null };
  retiradoEn: string; // fechas ISO en UTC
  devueltoEn: string | null; // null = todavia la tiene
  recordatorioEnviadoEn: string | null;
}

export interface FiltrosHistorial {
  aulaId?: number;
  usuarioId?: number;
  desde?: string; // AAAA-MM-DD, dia de Argentina
  hasta?: string;
  estado?: 'todos' | 'abiertos' | 'devueltos';
}

export interface UsuarioDetalle extends Usuario {
  activo: boolean;
  tieneClave: boolean; // false = todavia no uso el link del mail de alta
}

export interface LlaveEquipo {
  id: number;
  aula: string;
  rfidUid: string;
  slot: number | null; // null mientras esta prestada
  estado: EstadoLlave;
}

export interface Equipo {
  deviceId: string | null;
  online: boolean;
  ultimoContacto: string | null;
  slotsTotales: number;
  slotsReservados: number[];
  llaves: LlaveEquipo[];
}

/** Error que devuelve el servidor: { error: { codigo, mensaje } } */
export class ErrorApi extends Error {
  status: number; // 0 = no se pudo conectar
  codigo: string; // para decidir que hacer (ej. LLAVE_NO_DISPONIBLE)
  mensaje: string; // para mostrarle al usuario

  constructor(status: number, codigo: string, mensaje: string) {
    super(mensaje);
    this.status = status;
    this.codigo = codigo;
    this.mensaje = mensaje;
  }
}

interface Opciones {
  metodo?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  cuerpo?: unknown;
  // true en los pedidos que la web hace sola cada 5 s: no cuentan como actividad del usuario,
  // asi la sesion igual vence tras 60 s sin uso (US-01)
  automatico?: boolean;
}

async function pedir<T>(ruta: string, { metodo = 'GET', cuerpo, automatico }: Opciones = {}): Promise<T> {
  const encabezados: Record<string, string> = {};
  if (cuerpo !== undefined) encabezados['Content-Type'] = 'application/json';
  if (automatico) encabezados['X-Refresco-Automatico'] = '1';

  let respuesta: Response;
  try {
    respuesta = await fetch(`/api${ruta}`, {
      method: metodo,
      headers: encabezados,
      body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
    });
  } catch {
    throw new ErrorApi(0, 'SIN_CONEXION', 'No se pudo conectar con el servidor.');
  }

  if (!respuesta.ok) {
    const datos = await respuesta.json().catch(() => null);
    throw new ErrorApi(
      respuesta.status,
      datos?.error?.codigo ?? 'ERROR_DESCONOCIDO',
      datos?.error?.mensaje ?? 'Algo salió mal. Probá de nuevo.',
    );
  }
  // 204 y 202 sin datos
  const texto = await respuesta.text();
  return (texto ? JSON.parse(texto) : null) as T;
}

// { aulaId: 3, estado: 'todos' } -> "?aulaId=3&estado=todos" (sin los vacios)
function parametros(filtros: object): string {
  const pares = Object.entries(filtros).filter(([, v]) => v !== undefined && v !== '');
  return pares.length ? `?${new URLSearchParams(pares.map(([k, v]) => [k, String(v)]))}` : '';
}

export const api = {
  // Sin login
  estadoPublico: (automatico = false) => pedir<EstadoPublico>('/publico/estado', { automatico }),

  // Login (US-01, US-07, US-08)
  login: (email: string, clave: string) =>
    pedir<Usuario>('/auth/login', { metodo: 'POST', cuerpo: { email, clave } }),
  logout: () => pedir<null>('/auth/logout', { metodo: 'POST' }),
  yo: () => pedir<Usuario>('/auth/yo'),
  recuperar: (email: string) =>
    pedir<{ mensaje: string }>('/auth/recuperar', { metodo: 'POST', cuerpo: { email } }),
  restablecer: (token: string, claveNueva: string) =>
    pedir<null>('/auth/restablecer', { metodo: 'POST', cuerpo: { token, claveNueva } }),

  // Con login
  aulas: (automatico = false) => pedir<Aula[]>('/aulas', { automatico }),
  pedirLlave: (aulaId: number) => pedir<Reserva>('/reservas', { metodo: 'POST', cuerpo: { aulaId } }),
  reservaActiva: (automatico = false) => pedir<Reserva | null>('/reservas/activa', { automatico }),
  reserva: (id: number, automatico = false) => pedir<Reserva>(`/reservas/${id}`, { automatico }),
  cancelarReserva: (id: number) => pedir<null>(`/reservas/${id}`, { metodo: 'DELETE' }),
  misPrestamos: (automatico = false) => pedir<Prestamo[]>('/prestamos/mios', { automatico }), // US-17

  // Solo preceptor y admin
  cuentasBloqueadas: (automatico = false) => pedir<CuentaBloqueada[]>('/usuarios/bloqueados', { automatico }),
  desbloquear: (usuarioId: number) => pedir<null>(`/usuarios/${usuarioId}/desbloquear`, { metodo: 'POST' }),
  incidentes: (automatico = false) => pedir<Incidente[]>('/incidentes', { automatico }), // US-05
  historial: (filtros: FiltrosHistorial, automatico = false) => // US-12 y US-13
    pedir<{ prestamos: Prestamo[]; enPoder: number | null }>(`/prestamos${parametros(filtros)}`, { automatico }),
  recordatorio: (prestamoId: number) => // US-16
    pedir<Prestamo>(`/prestamos/${prestamoId}/recordatorio`, { metodo: 'POST' }),
  usuarios: (automatico = false) => pedir<UsuarioDetalle[]>('/usuarios', { automatico }), // US-09
  altaDocente: (datos: { nombre: string; apellido: string; email: string; telefono: string }) =>
    pedir<UsuarioDetalle>('/usuarios', { metodo: 'POST', cuerpo: datos }),
  cambiarActivo: (usuarioId: number, activo: boolean) =>
    pedir<UsuarioDetalle>(`/usuarios/${usuarioId}`, { metodo: 'PATCH', cuerpo: { activo } }),
  equipo: (automatico = false) => pedir<Equipo>('/equipo', { automatico }),
  cambiarRfid: (llaveId: number, rfidUid: string) => // US-10
    pedir<LlaveEquipo>(`/llaves/${llaveId}/rfid`, { metodo: 'PUT', cuerpo: { rfidUid } }),
};
