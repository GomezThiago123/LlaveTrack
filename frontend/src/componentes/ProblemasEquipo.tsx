// US-05 y US-21: el preceptor ve las fallas del equipo (ej. no encontro la llave pedida), para
// entregarla a mano y pedir que lo revisen. Mientras un incidente esta abierto, su aula figura
// "En revision" y no se puede reservar; al marcarlo resuelto, vuelve a estar disponible.
// Muestra los abiertos (de cualquier dia) y los resueltos hoy. Solo aparece si hay alguno.
// Se actualiza cada 5 s.
import { useCallback, useEffect, useState } from 'react';
import { api, type Incidente } from '../api';
import { useSesion } from '../sesion';
import { hora, nombreAula, REFRESCO_MS, useIntervalo } from '../utiles';
import { Alerta } from './Comunes';

export default function ProblemasEquipo() {
  const { manejarError } = useSesion();
  const [incidentes, setIncidentes] = useState<Incidente[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [resolviendo, setResolviendo] = useState<number | null>(null);

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

  async function resolver(incidente: Incidente) {
    setResolviendo(incidente.id);
    try {
      await api.resolverIncidente(incidente.id);
      await cargar();
    } catch (err) {
      setError(manejarError(err));
    } finally {
      setResolviendo(null);
    }
  }

  if (incidentes.length === 0 && !error) return null;
  const abiertos = incidentes.filter((i) => !i.resueltoEn).length;

  return (
    <section className="tarjeta problemas">
      <h2>{abiertos ? `Incidentes del equipo (${abiertos} sin resolver)` : 'Incidentes del equipo'}</h2>
      <Alerta>{error}</Alerta>
      <ul className="lista">
        {incidentes.map((incidente) => (
          <li key={incidente.id} className={incidente.resueltoEn ? 'suave' : undefined}>
            <strong>
              {hora(incidente.ocurridoEn)} · {incidente.descripcion}
            </strong>
            {(incidente.aula || incidente.docente) && (
              <span className="suave chico">
                {' '}
                {[incidente.aula && nombreAula(incidente.aula), incidente.docente].filter(Boolean).join(' · ')}
              </span>
            )}
            <div className="chico">
              {incidente.resueltoEn ? (
                <span>
                  Resuelto a las {hora(incidente.resueltoEn)}
                  {incidente.resueltoPor && ` por ${incidente.resueltoPor}`}
                </span>
              ) : (
                <>
                  {incidente.aula && <span className="suave">El aula figura "En revisión". </span>}
                  <button
                    type="button"
                    className="boton-texto chico"
                    onClick={() => resolver(incidente)}
                    disabled={resolviendo === incidente.id}
                  >
                    Marcar resuelto
                  </button>
                </>
              )}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
