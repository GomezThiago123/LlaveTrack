// Vista publica (US-02): que llaves hay, sin datos personales y sin login.
import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router';
import { api, type EstadoPublico } from '../api';
import { Alerta, ChipEstado, EstadoEquipo, Pagina } from '../componentes/Comunes';
import { useSesion } from '../sesion';
import { nombreAula, REFRESCO_MS, useIntervalo } from '../utiles';

export default function Inicio() {
  const { usuario } = useSesion();
  const [estado, setEstado] = useState<EstadoPublico | null>(null);
  const [error, setError] = useState<string | null>(null);

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

  return (
    <Pagina>
      <h1>Llaves de las aulas</h1>
      <EstadoEquipo online={estado?.equipoOnline ?? null} />
      <Alerta>{error}</Alerta>

      {estado && (
        <ul className="lista">
          {estado.aulas.map((aula) => (
            <li key={aula.id} className="tarjeta fila">
              <span className="aula-nombre">{nombreAula(aula.nombre)}</span>
              <ChipEstado estado={aula.estado} />
            </li>
          ))}
        </ul>
      )}

      <Link to={usuario ? '/aulas' : '/login'} className="boton boton-ancho">
        {usuario ? 'Pedir una llave' : 'Ingresar para pedir una llave'}
      </Link>
    </Pagina>
  );
}
