// Faltantes (preceptor): que llaves estan fuera del carrusel, quien las tiene y desde cuando.
// Desde aca se le manda un recordatorio por mail al docente (US-16). Se actualiza cada 5 s.
import { useState } from 'react';
import { BellRing, Check, Mail, Phone } from 'lucide-react';
import { api, type Prestamo } from '../api';
import { Alerta, EtiquetaSeccion, PaginaApp } from '../componentes/Comunes';
import { useRefresco } from '../refresco';
import { useSesion } from '../sesion';
import { duracion, hora } from '../utiles';

// US-16: a la hora sin devolver, la llave se marca "Demorada"
const DEMORA_MS = 60 * 60 * 1000;

export default function Faltantes() {
  const abiertos = useRefresco((automatico) => api.historial({ estado: 'abiertos' }, automatico));
  const aulas = useRefresco((automatico) => api.aulas(automatico));
  const prestamos = [...(abiertos.datos?.prestamos ?? [])].reverse(); // el que hace mas que la tiene, primero
  const total = aulas.datos?.length ?? 0;

  return (
    <PaginaApp titulo="Faltantes">
      <section className="tarjeta">
        <p className="etiqueta-seccion">Fuera del carrusel</p>
        <div className="contador">
          <strong className={prestamos.length ? 'movimiento-abierto' : 'texto-ok'}>{prestamos.length}</strong>
          <span className="suave">/ {total} llaves</span>
        </div>
        <div className="barra-llaves" aria-hidden>
          {aulas.datos?.map((a) => (
            <span key={a.id} className={a.estado.toLowerCase()} title={`${a.nombre}: ${a.estado}`} />
          ))}
        </div>
      </section>

      <Alerta>{abiertos.error}</Alerta>
      <EtiquetaSeccion>Préstamos sin devolver</EtiquetaSeccion>
      {!abiertos.datos && !abiertos.error && <p className="cargando">Cargando…</p>}
      {abiertos.datos && prestamos.length === 0 && (
        <p className="tarjeta vacio">
          <Check size={20} aria-hidden /> Todas las llaves están en el carrusel.
        </p>
      )}
      <ul className="lista">
        {prestamos.map((p) => (
          <li key={p.id}>
            <TarjetaFaltante prestamo={p} alCambiar={() => abiertos.recargar()} />
          </li>
        ))}
      </ul>
    </PaginaApp>
  );
}

function TarjetaFaltante({ prestamo, alCambiar }: { prestamo: Prestamo; alCambiar: () => void }) {
  const { manejarError } = useSesion();
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const demorada = Date.now() - new Date(prestamo.retiradoEn).getTime() >= DEMORA_MS;
  const { docente } = prestamo;

  async function recordar() {
    setEnviando(true);
    setError(null);
    try {
      await api.recordatorio(prestamo.id);
      alCambiar();
    } catch (err) {
      setError(manejarError(err));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <article className="tarjeta">
      <div className="fila">
        <span className="cuadro-aula cuadro-aula-rojo">{prestamo.aula}</span>
        <div className="crece">
          <p>
            <strong>
              {docente.nombre} {docente.apellido}
            </strong>
          </p>
          <p className="mono suave chico">retiro {hora(prestamo.retiradoEn)}</p>
        </div>
        <span className={`demora ${demorada ? 'demora-larga' : ''}`}>
          {demorada ? 'Demorada · ' : 'Hace '}
          {duracion(prestamo.retiradoEn)}
        </span>
      </div>
      <div className="contacto">
        <span>
          <Mail size={14} aria-hidden />
          <a href={`mailto:${docente.email}`}>{docente.email}</a>
        </span>
        {docente.telefono && (
          <span>
            <Phone size={14} aria-hidden />
            <a href={`tel:${docente.telefono.replace(/\s/g, '')}`}>{docente.telefono}</a>
          </span>
        )}
      </div>
      <Alerta>{error}</Alerta>
      {prestamo.recordatorioEnviadoEn && (
        <p className="suave chico separado">
          Recordatorio enviado a las {hora(prestamo.recordatorioEnviadoEn)}.
        </p>
      )}
      <button
        type="button"
        className="boton boton-claro boton-chico boton-ancho separado"
        onClick={recordar}
        disabled={enviando}
      >
        <BellRing size={16} aria-hidden />
        {enviando ? 'Enviando…' : prestamo.recordatorioEnviadoEn ? 'Enviar otro recordatorio' : 'Enviar recordatorio'}
      </button>
    </article>
  );
}
