// Lista de aulas con login (US-02): buscador, pisos y "solo disponibles". Pedir una llave (US-03).
// Todos ven quien tiene cada llave, desde que hora y su telefono. Se actualiza cada 5 s.
import { useEffect, useState } from 'react';
import { Search } from 'lucide-react';
import { api, type Aula, type Reserva } from '../api';
import { Alerta, EtiquetaSeccion, Insignia, Interruptor, PaginaApp, PildoraEquipo, Segmentado } from '../componentes/Comunes';
import CuentasBloqueadas from '../componentes/CuentasBloqueadas';
import ProblemasEquipo from '../componentes/ProblemasEquipo';
import { TarjetaEnPoder, TarjetaReserva } from '../componentes/Reserva';
import { useRefresco } from '../refresco';
import { useSesion } from '../sesion';
import { esPreceptor, hora, piso } from '../utiles';

export default function Aulas() {
  const { usuario, manejarError } = useSesion();
  const aulas = useRefresco((automatico) => api.aulas(automatico));
  const estado = useRefresco((automatico) => api.estadoPublico(automatico));
  const [reserva, setReserva] = useState<Reserva | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pidiendo, setPidiendo] = useState<number | null>(null); // id del aula que se esta pidiendo
  const [busqueda, setBusqueda] = useState('');
  const [filtroPiso, setFiltroPiso] = useState('todas');
  const [soloDisponibles, setSoloDisponibles] = useState(false);

  // La reserva pendiente, si hay (tambien si se recargo la pagina)
  useEffect(() => {
    api
      .reservaActiva()
      .then(setReserva)
      .catch((err) => setError(manejarError(err)));
  }, [manejarError]);

  const equipoOnline = estado.datos?.equipoOnline ?? null;
  const lista = aulas.datos ?? [];
  const tieneReserva = reserva?.estado === 'PENDIENTE';
  const enMiPoder = lista.filter((a) => a.estado === 'PRESTADA' && a.tenedor?.usuarioId === usuario?.id);
  const disponibles = lista.filter((a) => a.estado === 'DISPONIBLE').length;
  const pisos = [...new Set(lista.map((a) => piso(a.nombre)).filter((p) => p !== null))].sort();
  const filtradas = lista.filter(
    (a) =>
      (filtroPiso === 'todas' || String(piso(a.nombre)) === filtroPiso) &&
      (!soloDisponibles || a.estado === 'DISPONIBLE') &&
      a.nombre.toLowerCase().includes(busqueda.trim().toLowerCase()),
  );
  // US-22: sin equipo no se puede retirar la llave. Se reactiva solo con el refresco
  // Por que no se puede pedir. Sin equipo, el boton lo dice (US-22: "Equipo desconectado");
  // con una reserva activa, lo dice un solo aviso arriba de la grilla.
  const motivo = equipoOnline === null ? 'Cargando…' : !equipoOnline ? 'Equipo desconectado' : null;

  async function pedir(aula: Aula) {
    setPidiendo(aula.id);
    setError(null);
    try {
      setReserva(await api.pedirLlave(aula.id));
      window.scrollTo({ top: 0, behavior: 'smooth' }); // el codigo aparece arriba de todo
    } catch (err) {
      setError(manejarError(err));
    } finally {
      setPidiendo(null);
      aulas.recargar(); // otro la pudo haber pedido justo antes: mostrar el estado real
    }
  }

  return (
    <PaginaApp titulo={`Hola, ${usuario?.nombre ?? ''}`} derecha={<PildoraEquipo online={equipoOnline} />}>
      {equipoOnline === false && (
        <Alerta>El equipo está desconectado: por ahora no entrega ni recibe llaves.</Alerta>
      )}
      {reserva && <TarjetaReserva reserva={reserva} alCambiar={setReserva} equipoOnline={equipoOnline} />}
      {enMiPoder.map((a) => (
        <TarjetaEnPoder key={a.id} aula={a.nombre} desde={a.tenedor!.desde} />
      ))}
      {usuario && esPreceptor(usuario.rol) && (
        <>
          <ProblemasEquipo />
          <CuentasBloqueadas />
        </>
      )}

      <div className="campo-busqueda">
        <Search size={18} aria-hidden />
        <input
          type="search"
          inputMode="numeric"
          placeholder="Buscar aula, ej. 204"
          aria-label="Buscar aula"
          value={busqueda}
          onChange={(e) => setBusqueda(e.target.value)}
        />
      </div>
      {pisos.length > 1 && (
        <Segmentado
          etiqueta="Filtrar por piso"
          valor={filtroPiso}
          alCambiar={setFiltroPiso}
          opciones={[
            { valor: 'todas', texto: `Todas (${lista.length})` },
            ...pisos.map((p) => ({ valor: String(p), texto: `Piso ${p}` })),
          ]}
        />
      )}
      <div className="tarjeta fila">
        <span>
          Solo disponibles <span className="mono texto-ok">({disponibles})</span>
        </span>
        <Interruptor activo={soloDisponibles} alCambiar={setSoloDisponibles} etiqueta="Mostrar solo las disponibles" />
      </div>

      <Alerta>{error ?? aulas.error}</Alerta>
      {tieneReserva && equipoOnline && (
        <Alerta tipo="aviso">Ya tenés una reserva: usala o cancelala para pedir otra llave.</Alerta>
      )}
      <EtiquetaSeccion derecha={`${filtradas.length} resultados`}>Aulas</EtiquetaSeccion>
      {!aulas.datos && !aulas.error && <p className="cargando">Cargando…</p>}
      {aulas.datos && filtradas.length === 0 && <p className="vacio">No hay aulas que coincidan.</p>}
      <ul className="grilla">
        {filtradas.map((aula) => (
          <li key={aula.id}>
            <TarjetaAula
              aula={aula}
              esMia={aula.tenedor?.usuarioId === usuario?.id}
              motivo={motivo}
              bloqueada={tieneReserva}
              pidiendo={pidiendo === aula.id}
              alPedir={() => pedir(aula)}
            />
          </li>
        ))}
      </ul>
    </PaginaApp>
  );
}

function TarjetaAula({
  aula,
  esMia,
  motivo,
  bloqueada,
  pidiendo,
  alPedir,
}: {
  aula: Aula;
  esMia: boolean;
  motivo: string | null; // por que no se puede pedir, para mostrar en el boton
  bloqueada: boolean; // ya tiene una reserva: el boton queda deshabilitado sin texto extra
  pidiendo: boolean;
  alPedir: () => void;
}) {
  const numerica = /^\d/.test(aula.nombre);
  return (
    <article className={`aula aula-${aula.estado.toLowerCase()}`}>
      <div className="aula-titulo">
        <div>
          {numerica && <small>Aula</small>}
          <span className={`aula-numero ${numerica ? '' : 'aula-numero-texto'}`}>
            {aula.nombre}
          </span>
        </div>
      </div>
      <Insignia estado={aula.estado} />
      {aula.estado === 'DISPONIBLE' ? (
        <button type="button" className="boton boton-chico" disabled={motivo !== null || bloqueada || pidiendo} onClick={alPedir}>
          {pidiendo ? 'Pidiendo…' : (motivo ?? 'Pedir llave')}
        </button>
      ) : (
        aula.tenedor && (
          <p className="aula-tenedor">
            {esMia ? (
              <strong>{aula.estado === 'RESERVADA' ? 'Tu reserva' : 'En tu poder'}</strong>
            ) : (
              <>
                {aula.estado === 'PRESTADA' ? 'La tiene' : 'Reservada por'}{' '}
                <strong>
                  {aula.tenedor.nombre} {aula.tenedor.apellido}
                </strong>
                <br />
                <span className="mono">desde {hora(aula.tenedor.desde)}</span>
                {aula.tenedor.telefono && (
                  <>
                    <br />
                    <a href={`tel:${aula.tenedor.telefono.replace(/\s/g, '')}`}>{aula.tenedor.telefono}</a>
                  </>
                )}
              </>
            )}
          </p>
        )
      )}
    </article>
  );
}
