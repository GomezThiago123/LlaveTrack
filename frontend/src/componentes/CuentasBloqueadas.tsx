// US-07: el preceptor ve las cuentas bloqueadas por intentos fallidos y las puede
// desbloquear antes de los 15 min. Solo aparece si hay alguna. Se actualiza cada 5 s.
import { useCallback, useEffect, useState } from 'react';
import { api, type CuentaBloqueada } from '../api';
import { useSesion } from '../sesion';
import { hora, REFRESCO_MS, useIntervalo } from '../utiles';
import { Alerta } from './Comunes';

export default function CuentasBloqueadas() {
  const { manejarError } = useSesion();
  const [cuentas, setCuentas] = useState<CuentaBloqueada[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [desbloqueando, setDesbloqueando] = useState<number | null>(null); // id de la cuenta

  const cargar = useCallback(
    async (automatico = false) => {
      try {
        setCuentas(await api.cuentasBloqueadas(automatico));
      } catch (err) {
        setError(manejarError(err));
      }
    },
    [manejarError],
  );

  useEffect(() => {
    cargar();
  }, [cargar]);
  useIntervalo(() => cargar(true), REFRESCO_MS);

  async function desbloquear(cuenta: CuentaBloqueada) {
    setDesbloqueando(cuenta.id);
    setError(null);
    try {
      await api.desbloquear(cuenta.id);
      await cargar();
    } catch (err) {
      setError(manejarError(err));
    } finally {
      setDesbloqueando(null);
    }
  }

  if (cuentas.length === 0 && !error) return null;

  return (
    <section className="tarjeta bloqueadas">
      <h2>Cuentas bloqueadas</h2>
      <Alerta>{error}</Alerta>
      <ul className="lista">
        {cuentas.map((cuenta) => (
          <li key={cuenta.id} className="fila">
            <span>
              <strong>
                {cuenta.nombre} {cuenta.apellido}
              </strong>
              <br />
              <span className="tenedor">Bloqueada hasta las {hora(cuenta.bloqueadoHasta)}</span>
            </span>
            <button
              type="button"
              className="boton"
              disabled={desbloqueando !== null}
              onClick={() => desbloquear(cuenta)}
            >
              {desbloqueando === cuenta.id ? 'Desbloqueando…' : 'Desbloquear'}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
