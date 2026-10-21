// Vista publica (US-02): que llaves hay, sin datos personales y sin login. Se actualiza cada 5 s.
import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router';
import { api, type EstadoPublico } from '../api';
import { Alerta, EtiquetaSeccion, Insignia, PaginaSimple, PildoraEquipo } from '../componentes/Comunes';
import { useSesion } from '../sesion';
import { REFRESCO_MS, useIntervalo } from '../utiles';

export default function Inicio() {
  const { usuario } = useSesion();
  const [estado, setEstado] = useState<EstadoPublico | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Sin login no hay sesion que vencer: por eso no usa useRefresco (que lleva al login si hay 401)
  const cargar = useCallback((automatico = false) => {
    api
      .estadoPublico(automatico)
      .then((datos) => {
        setEstado(datos);
        setError(null);
      })
      .catch(() => setError('No se pudo conectar con el servidor. Reintentando…'));
  }, []);

  useEffect(() => cargar(), [cargar]);
  useIntervalo(() => cargar(true), REFRESCO_MS);

  const disponibles = estado?.aulas.filter((a) => a.estado === 'DISPONIBLE').length ?? 0;

  return (
    <PaginaSimple subtitulo="Qué llaves hay ahora">
      <Link to={usuario ? '/aulas' : '/login'} className="boton boton-ancho">
        {usuario ? 'Pedir una llave' : 'Ingresar para pedir una llave'}
      </Link>
      <div className="fila">
        <PildoraEquipo online={estado?.equipoOnline ?? null} />
        {estado && <span className="suave chico">{disponibles} disponibles</span>}
      </div>
      <Alerta>{error}</Alerta>
      {!estado && !error && <p className="cargando">Cargando…</p>}

      {estado && (
        <>
          <EtiquetaSeccion derecha={`${estado.aulas.length} aulas`}>Aulas</EtiquetaSeccion>
          <ul className="grilla">
            {estado.aulas.map((aula) => (
              <li key={aula.id}>
                <article className={`aula aula-${aula.estado.toLowerCase()}`}>
                  <div className="aula-titulo">
                    <div>
                      {/^\d/.test(aula.nombre) && <small>Aula</small>}
                      <span className={`aula-numero ${/^\d/.test(aula.nombre) ? '' : 'aula-numero-texto'}`}>
                        {aula.nombre}
                      </span>
                    </div>
                  </div>
                  <Insignia estado={aula.estado} />
                </article>
              </li>
            ))}
          </ul>
        </>
      )}
    </PaginaSimple>
  );
}
