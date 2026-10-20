import { useEffect, useRef } from 'react';
import type { EstadoLlave } from './api';

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
const formatoHora = new Intl.DateTimeFormat('es-AR', {
  timeZone: 'America/Argentina/Buenos_Aires',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23', // 14:30, no 02:30 p. m.
});

export function hora(fechaIso: string): string {
  return formatoHora.format(new Date(fechaIso));
}

export const TEXTO_ESTADO: Record<EstadoLlave, string> = {
  DISPONIBLE: 'Disponible',
  RESERVADA: 'Reservada',
  PRESTADA: 'Prestada',
  BAJA: 'De baja',
};

// "214" -> "Aula 214"; "Laboratorio 1" queda igual
export function nombreAula(nombre: string): string {
  return /^\d/.test(nombre) ? `Aula ${nombre}` : nombre;
}

// Para usar dentro de una frase: "la llave del aula 214" / "la llave de Laboratorio 1"
export function delAula(nombre: string): string {
  return /^\d/.test(nombre) ? `del aula ${nombre}` : `de ${nombre}`;
}
