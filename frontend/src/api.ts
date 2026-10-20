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
  tenedor: { nombre: string; apellido: string; telefono: string | null; desde: string } | null;
}

export interface Reserva {
  id: number;
  aula: string;
  codigo: string;
  expiraEn: string; // fecha ISO en UTC
  estado: EstadoReserva;
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
  metodo?: 'GET' | 'POST' | 'DELETE';
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
};
