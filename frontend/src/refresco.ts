// Datos que cada pantalla pide al abrirse y vuelve a pedir sola cada 5 s.
import { useCallback, useEffect, useRef, useState } from 'react';
import { useSesion } from './sesion';
import { REFRESCO_MS, useIntervalo } from './utiles';

/**
 * Uso: const { datos, error, recargar } = useRefresco((automatico) => api.aulas(automatico));
 *
 * El primer pedido cuenta como actividad del usuario; los de cada 5 s van como automaticos
 * y no renuevan la sesion (US-01). Si la sesion vencio, manejarError lleva al login.
 */
export function useRefresco<T>(pedido: (automatico: boolean) => Promise<T>) {
  const { manejarError } = useSesion();
  const [datos, setDatos] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const ultimoPedido = useRef(pedido);
  ultimoPedido.current = pedido; // el mas nuevo (ej. con otros filtros), sin reiniciar nada

  const recargar = useCallback(
    async (automatico = false) => {
      try {
        setDatos(await ultimoPedido.current(automatico));
        setError(null);
      } catch (err) {
        setError(manejarError(err));
      }
    },
    [manejarError],
  );

  useEffect(() => {
    recargar();
  }, [recargar]);
  useIntervalo(() => recargar(true), REFRESCO_MS);

  return { datos, error, recargar };
}
