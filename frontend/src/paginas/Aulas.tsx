// Lista de aulas con login (US-02): pedir una llave (US-03). Se actualiza cada 5 s.
// Todos ven quien tiene cada llave, desde que hora y su telefono.
import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router';
import { api, type Aula, type Reserva } from '../api';
import { Alerta, ChipEstado, EstadoEquipo, Pagina } from '../componentes/Comunes';
import CuentasBloqueadas from '../componentes/CuentasBloqueadas';
import ProblemasEquipo from '../componentes/ProblemasEquipo';
import { useSesion } from '../sesion';
import { delAula, hora, nombreAula, REFRESCO_MS, useIntervalo } from '../utiles';

export default function Aulas() {
  const { usuario, manejarError } = useSesion();
  const navegar = useNavigate();
  const [aulas, setAulas] = useState<Aula[] | null>(null);
  const [equipoOnline, setEquipoOnline] = useState<boolean | null>(null);
  const [activa, setActiva] = useState<Reserva | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pidiendo, setPidiendo] = useState<number | null>(null); // id del aula que se esta pidiendo

  const cargar = useCallback(
    async (automatico = false) => {
      try {
        const [lista, estado, reserva] = await Promise.all([
          api.aulas(automatico),
          api.estadoPublico(automatico),
          api.reservaActiva(automatico),
        ]);
        setAulas(lista);
        setEquipoOnline(estado.equipoOnline);
        setActiva(reserva);
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

  async function pedir(aula: Aula) {
    setPidiendo(aula.id);
    setError(null);
    try {
      await api.pedirLlave(aula.id);
      navegar('/codigo');
    } catch (err) {
      setError(manejarError(err));
      cargar(); // otro la pudo haber pedido justo antes: mostrar el estado real
    } finally {
      setPidiendo(null);
    }
  }

  return (
    <Pagina>
      <h1>Aulas</h1>
      <EstadoEquipo online={equipoOnline} />
      {usuario && usuario.rol !== 'DOCENTE' && (
        <>
          <ProblemasEquipo />
          <CuentasBloqueadas />
        </>
      )}

      {activa && (
        <Link to="/codigo" className="tarjeta tarjeta-destacada">
          <strong>Tenés un código para la llave {delAula(activa.aula)}</strong>
          <span>Tocá acá para verlo →</span>
        </Link>
      )}

      <Alerta>{error}</Alerta>
      {!aulas && !error && <p className="cargando">Cargando…</p>}

      <ul className="lista">
        {aulas?.map((aula) => (
          <li key={aula.id} className="tarjeta">
            <div className="fila">
              <span className="aula-nombre">{nombreAula(aula.nombre)}</span>
              <ChipEstado estado={aula.estado} />
            </div>

            {aula.tenedor && (
              <p className="tenedor">
                {aula.estado === 'PRESTADA' ? 'La tiene' : 'Reservada por'}{' '}
                <strong>
                  {aula.tenedor.nombre} {aula.tenedor.apellido}
                </strong>{' '}
                desde las {hora(aula.tenedor.desde)}
                {aula.tenedor.telefono && (
                  <>
                    {' · '}
                    <a className="telefono" href={`tel:${aula.tenedor.telefono.replace(/\s/g, '')}`}>{aula.tenedor.telefono}</a>
                  </>
                )}
              </p>
            )}

            {aula.estado === 'DISPONIBLE' && !activa && (
              // US-22: sin equipo no se puede retirar la llave. Se reactiva solo con el refresco
              <button
                type="button"
                className="boton boton-ancho"
                disabled={pidiendo !== null || !equipoOnline}
                onClick={() => pedir(aula)}
              >
                {!equipoOnline ? 'Equipo desconectado' : pidiendo === aula.id ? 'Pidiendo…' : 'Pedir llave'}
              </button>
            )}
          </li>
        ))}
      </ul>
    </Pagina>
  );
}
