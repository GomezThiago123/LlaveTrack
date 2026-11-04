// Historial de retiros y devoluciones (US-12 por aula, US-13 por docente), para el preceptor.
// Los retiros sin devolver van en rojo. Por defecto muestra los ultimos 7 dias.
import { useEffect, useState } from 'react';
import { Download } from 'lucide-react';
import { api, urlExportarHistorial, type FiltrosHistorial } from '../api';
import { Alerta, EtiquetaSeccion, PaginaApp, Segmentado } from '../componentes/Comunes';
import { useRefresco } from '../refresco';
import { diaIso, duracion, fechaCorta, hora, nombreAula } from '../utiles';

type Estado = NonNullable<FiltrosHistorial['estado']>;

export default function Historial() {
  const [aulaId, setAulaId] = useState('');
  const [usuarioId, setUsuarioId] = useState('');
  const [desde, setDesde] = useState(diaIso(new Date(Date.now() - 6 * 86_400_000)));
  const [hasta, setHasta] = useState(diaIso());
  const [estado, setEstado] = useState<Estado>('todos');

  const aulas = useRefresco((automatico) => api.aulas(automatico));
  const usuarios = useRefresco((automatico) => api.usuarios(automatico));
  const filtros: FiltrosHistorial = {
    aulaId: aulaId ? Number(aulaId) : undefined,
    usuarioId: usuarioId ? Number(usuarioId) : undefined,
    desde: desde || undefined,
    hasta: hasta || undefined,
    estado,
  };
  const historial = useRefresco((automatico) => api.historial(filtros, automatico));
  const { recargar } = historial;
  const bajas = useRefresco((automatico) => api.bajas(aulaId ? Number(aulaId) : undefined, automatico)); // US-11
  const recargarBajas = bajas.recargar;
  useEffect(() => {
    recargarBajas();
  }, [aulaId, recargarBajas]);

  // Al cambiar un filtro se pide de nuevo enseguida (no hay que esperar los 5 s)
  useEffect(() => {
    recargar();
  }, [aulaId, usuarioId, desde, hasta, estado, recargar]);

  const prestamos = historial.datos?.prestamos ?? [];
  const docente = usuarios.datos?.find((u) => String(u.id) === usuarioId);

  return (
    <PaginaApp titulo="Historial">
      <section className="tarjeta formulario">
        <div className="dos-columnas">
          <label>
            Aula
            <select value={aulaId} onChange={(e) => setAulaId(e.target.value)}>
              <option value="">Todas</option>
              {aulas.datos?.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.nombre}
                </option>
              ))}
            </select>
          </label>
          <label>
            Docente
            <select value={usuarioId} onChange={(e) => setUsuarioId(e.target.value)}>
              <option value="">Todos</option>
              {usuarios.datos?.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.apellido}, {u.nombre}
                </option>
              ))}
            </select>
          </label>
          <label>
            Desde
            <input type="date" value={desde} max={hasta || undefined} onChange={(e) => setDesde(e.target.value)} />
          </label>
          <label>
            Hasta
            <input type="date" value={hasta} min={desde || undefined} onChange={(e) => setHasta(e.target.value)} />
          </label>
        </div>
        <Segmentado
          etiqueta="Filtrar por estado"
          valor={estado}
          alCambiar={setEstado}
          opciones={[
            { valor: 'todos', texto: 'Todos' },
            { valor: 'devueltos', texto: 'Devueltas' },
            { valor: 'abiertos', texto: 'Sin devolver' },
          ]}
        />
      </section>

      {/* US-13: cuantas llaves tiene hoy el docente elegido */}
      {docente && historial.datos?.enPoder != null && (
        <Alerta tipo={historial.datos.enPoder ? 'aviso' : 'ok'}>
          {docente.nombre} {docente.apellido} tiene hoy {historial.datos.enPoder}{' '}
          {historial.datos.enPoder === 1 ? 'llave' : 'llaves'} en su poder.
        </Alerta>
      )}
      <Alerta>{historial.error}</Alerta>

      <EtiquetaSeccion
        derecha={
          <span className="fila">
            {prestamos.length} movimientos
            {/* US-19: el mismo listado, con los mismos filtros. Sin movimientos, deshabilitado */}
            {prestamos.length > 0 ? (
              <a className="boton-texto chico" href={urlExportarHistorial(filtros)} download>
                <Download size={14} /> Exportar a Excel
              </a>
            ) : (
              <button type="button" className="boton-texto chico" disabled>
                <Download size={14} /> Exportar a Excel
              </button>
            )}
          </span>
        }
      >
        Retiros y devoluciones
      </EtiquetaSeccion>
      {!historial.datos && !historial.error && <p className="cargando">Cargando…</p>}
      {historial.datos && prestamos.length === 0 && <p className="tarjeta vacio">No hay movimientos para este período.</p>}
      {prestamos.length > 0 && (
        <ul className="tarjeta lista-divisiones">
          {prestamos.map((p) => {
            const abierto = p.devueltoEn === null;
            return (
              <li key={p.id} className={`fila ${abierto ? 'movimiento-abierto' : ''}`}>
                <span className={`cuadro-aula ${abierto ? 'cuadro-aula-rojo' : ''}`} title={nombreAula(p.aula)}>
                  {p.aula}
                </span>
                <div className="crece">
                  <p>
                    <strong>
                      {p.docente.nombre} {p.docente.apellido}
                    </strong>
                  </p>
                  <p className="mono chico">
                    {fechaCorta(p.retiradoEn)} · {hora(p.retiradoEn)} → {abierto ? '--:--' : hora(p.devueltoEn!)}
                  </p>
                </div>
                <span className="mono chico">
                  {abierto ? 'Sin devolver' : p.perdida ? 'Perdida' : duracion(p.retiradoEn, p.devueltoEn)}
                </span>
              </li>
            );
          })}
        </ul>
      )}

      {bajas.datos && bajas.datos.length > 0 && (
        <>
          <EtiquetaSeccion>Llaves dadas de baja</EtiquetaSeccion>
          <ul className="tarjeta lista-divisiones">
            {bajas.datos.map((b) => (
              <li key={b.id} className="fila">
                <span className="cuadro-aula cuadro-aula-rojo" title={nombreAula(b.aula)}>
                  {b.aula}
                </span>
                <div className="crece">
                  <p>
                    <strong>{b.motivo}</strong>
                  </p>
                  <p className="chico suave">
                    {fechaCorta(b.dadaEn)} · {hora(b.dadaEn)} · la dio de baja {b.preceptor}
                    {b.ultimoDocente && ` · la tuvo por última vez ${b.ultimoDocente}`}
                  </p>
                </div>
                <span className="mono chico suave">{b.rfidUid}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </PaginaApp>
  );
}
