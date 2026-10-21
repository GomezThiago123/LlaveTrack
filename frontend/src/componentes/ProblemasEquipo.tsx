// US-05: el preceptor ve las fallas del equipo de hoy (ej. no encontro la llave pedida),
// para entregarla a mano y pedir que lo revisen. Solo aparece si hubo alguna. Se actualiza cada 5 s.
// Marcarlas como resueltas es US-21 (V2).
import { useCallback, useEffect, useState } from 'react';
import { api, type Incidente } from '../api';
import { useSesion } from '../sesion';
import { hora, nombreAula, REFRESCO_MS, useIntervalo } from '../utiles';
import { Alerta } from './Comunes';

export default function ProblemasEquipo() {
  const { manejarError } = useSesion();
  const [incidentes, setIncidentes] = useState<Incidente[]>([]);
  const [error, setError] = useState<string | null>(null);

  const cargar = useCallback(
    async (automatico = false) => {
      try {
        setIncidentes(await api.incidentes(automatico));
        setError(null);
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

  if (incidentes.length === 0 && !error) return null;

  return (
    <section className="tarjeta problemas">
      <h2>Problemas del equipo hoy</h2>
      <Alerta>{error}</Alerta>
      <ul className="lista">
        {incidentes.map((incidente) => (
          <li key={incidente.id}>
            <strong>
              {hora(incidente.ocurridoEn)} · {incidente.descripcion}
            </strong>
            {(incidente.aula || incidente.docente) && (
              <span className="suave chico">
                {' '}
                {[incidente.aula && nombreAula(incidente.aula), incidente.docente].filter(Boolean).join(' · ')}
              </span>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
