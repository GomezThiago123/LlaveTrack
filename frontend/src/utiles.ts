import { useEffect, useRef } from 'react';
import type { EstadoLlave, Rol } from './api';

// Cada cuanto se actualizan solas las pantallas con datos que cambian (aulas, codigo)
export const REFRESCO_MS = 5000;

/**
 * Ejecuta `accion` cada `ms` milisegundos mientras la pantalla esta abierta.
 * Si la pestaña esta oculta (celular bloqueado, otra pestaña) no hace pedidos de más.
 */
export function useIntervalo(accion: () => void, ms: number) {
  const ultima = useRef(accion);
  ultima.current = accion; // siempre la version mas nueva, sin reiniciar el intervalo

  useEffect(() => {
    const id = setInterval(() => {
      if (!document.hidden) ultima.current();
    }, ms);
    return () => clearInterval(id);
  }, [ms]);
}

// La base guarda las horas en UTC; se muestran en hora de Argentina
const ZONA = 'America/Argentina/Buenos_Aires';
const formatoHora = new Intl.DateTimeFormat('es-AR', {
  timeZone: ZONA,
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23', // 14:30, no 02:30 p. m.
});
const formatoDia = new Intl.DateTimeFormat('en-CA', { timeZone: ZONA }); // en-CA da AAAA-MM-DD
const formatoFecha = new Intl.DateTimeFormat('es-AR', { timeZone: ZONA, day: '2-digit', month: '2-digit' });

export function hora(fechaIso: string): string {
  return formatoHora.format(new Date(fechaIso));
}

/** Dia de Argentina como AAAA-MM-DD (para los filtros de fecha). */
export function diaIso(fecha: Date = new Date()): string {
  return formatoDia.format(fecha);
}

/** "Hoy", "Ayer" o "20/10" */
export function fechaCorta(fechaIso: string): string {
  const dia = diaIso(new Date(fechaIso));
  if (dia === diaIso()) return 'Hoy';
  if (dia === diaIso(new Date(Date.now() - 86_400_000))) return 'Ayer';
  return formatoFecha.format(new Date(fechaIso));
}

/** 135 minutos -> "2h 15m"; 40 -> "40m" */
export function duracion(desdeIso: string, hastaIso?: string | null): string {
  const hasta = hastaIso ? new Date(hastaIso).getTime() : Date.now();
  const minutos = Math.max(0, Math.floor((hasta - new Date(desdeIso).getTime()) / 60_000));
  const h = Math.floor(minutos / 60);
  return h ? `${h}h ${String(minutos % 60).padStart(2, '0')}m` : `${minutos}m`;
}

export const TEXTO_ESTADO: Record<EstadoLlave, string> = {
  DISPONIBLE: 'Disponible',
  RESERVADA: 'Reservada',
  PRESTADA: 'Ocupada', // US-02: en la base sigue siendo PRESTADA
  BAJA: 'De baja',
};

export const TEXTO_ROL: Record<Rol, string> = {
  DOCENTE: 'Docente',
  PRECEPTOR: 'Preceptor',
  ADMIN: 'Admin',
};

/** Preceptores y administradores ven la parte de control (faltantes, historial, equipo). */
export function esPreceptor(rol: Rol): boolean {
  return rol !== 'DOCENTE';
}

// "214" -> "Aula 214"; "Laboratorio 1" queda igual
export function nombreAula(nombre: string): string {
  return /^\d/.test(nombre) ? `Aula ${nombre}` : nombre;
}

// Para usar dentro de una frase: "la llave del aula 214" / "la llave de Laboratorio 1"
export function delAula(nombre: string): string {
  return /^\d/.test(nombre) ? `del aula ${nombre}` : `de ${nombre}`;
}

/** El peine sale del primer numero del aula: 214 -> 2. Null si el nombre no empieza con un numero. */
export function peine(nombre: string): number | null {
  return /^\d/.test(nombre) ? Number(nombre[0]) : null;
}
