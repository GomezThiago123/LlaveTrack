// El equipo, para el preceptor: si esta conectado, que hay en cada slot del carrusel, los problemas
// de hoy (US-05) y el tag RFID de cada aula, que se puede cambiar (US-10). Se actualiza cada 5 s.
import { useState, type FormEvent } from 'react';
import { Check, Pencil, X } from 'lucide-react';
import { api, type Equipo as DatosEquipo, type LlaveEquipo } from '../api';
import { Alerta, EtiquetaSeccion, Insignia, PaginaApp, PildoraEquipo } from '../componentes/Comunes';
import ProblemasEquipo from '../componentes/ProblemasEquipo';
import { useRefresco } from '../refresco';
import { useSesion } from '../sesion';
import { hora } from '../utiles';

export default function Equipo() {
  const { datos, error, recargar } = useRefresco((automatico) => api.equipo(automatico));
  const [verTodas, setVerTodas] = useState(false);
  const llaves = datos?.llaves ?? [];
  const enDisco = llaves.filter((l) => l.slot !== null).length;

  return (
    <PaginaApp titulo="Equipo" derecha={<PildoraEquipo online={datos?.online ?? null} />}>
      <Alerta>{error}</Alerta>
      {!datos && !error && <p className="cargando">Cargando…</p>}
      {datos && (
        <>
          <section className="tarjeta">
            <div className="fila">
              <h2 className="mono">{datos.deviceId ?? 'Sin equipo'}</h2>
              <span className={`insignia ${datos.online ? 'insignia-disponible' : 'insignia-prestada'}`}>
                {datos.online ? 'En línea' : 'Desconectado'}
              </span>
            </div>
            <dl className="datos">
              <div>
                <dt>Último contacto</dt>
                <dd>{datos.ultimoContacto ? hace(datos.ultimoContacto) : '—'}</dd>
              </div>
              <div>
                <dt>Slots</dt>
                <dd>{datos.slotsTotales}</dd>
              </div>
              <div>
                <dt>Llaves en el disco</dt>
                <dd>
                  {enDisco}/{llaves.length}
                </dd>
              </div>
              <div>
                <dt>Slot HOME</dt>
                <dd>{datos.slotsReservados.join(', ') || '—'}</dd>
              </div>
            </dl>
          </section>

          {datos.slotsTotales > 0 && (
            <section className="tarjeta">
              <Carrusel equipo={datos} />
              <div className="leyenda">
                <span>
                  <i className="disponible" />
                  Llave en el disco
                </span>
                <span>
                  <i className="reservada" />
                  Reservada
                </span>
                <span>
                  <i />
                  Vacío
                </span>
                <span>
                  <i className="home" />
                  HOME
                </span>
              </div>
            </section>
          )}
        </>
      )}

      <ProblemasEquipo />

      {datos && (
        <>
          <EtiquetaSeccion
            derecha={
              llaves.length > 8 && (
                <button type="button" className="boton-texto chico" onClick={() => setVerTodas(!verTodas)}>
                  {verTodas ? 'Ver menos' : `Ver las ${llaves.length}`}
                </button>
              )
            }
          >
            Tags RFID
          </EtiquetaSeccion>
          <ul className="tarjeta lista-divisiones">
            {(verTodas ? llaves : llaves.slice(0, 8)).map((llave) => (
              <FilaLlave key={`${llave.id}-${llave.rfidUid}`} llave={llave} alGuardar={() => recargar()} />
            ))}
          </ul>
          <p className="suave chico">
            Los UID reales los muestra el modo diagnóstico del equipo (mantener <kbd>D</kbd> al encenderlo).
          </p>
        </>
      )}
    </PaginaApp>
  );
}

/** Los slots en circulo, el 0 (HOME) arriba. Las llaves prestadas no estan en el disco. */
function Carrusel({ equipo }: { equipo: DatosEquipo }) {
  const porSlot = new Map(equipo.llaves.filter((l) => l.slot !== null).map((l) => [l.slot!, l]));
  const total = equipo.slotsTotales;
  return (
    <div className="carrusel" role="img" aria-label={`Carrusel de ${total} slots`}>
      <div className="carrusel-aro" />
      {Array.from({ length: total }, (_, slot) => {
        const llave = porSlot.get(slot);
        const clase = equipo.slotsReservados.includes(slot)
          ? 'home'
          : llave?.estado === 'RESERVADA'
            ? 'reservada'
            : llave
              ? 'disponible'
              : '';
        const angulo = (slot * 360) / total;
        return (
          <span
            key={slot}
            className={`carrusel-slot ${clase}`}
            // Gira hasta su lugar en el aro y "desgira" el numero para que se lea derecho
            style={{ transform: `rotate(${angulo}deg) translateY(-104px) rotate(${-angulo}deg)` }}
            title={llave ? `Slot ${slot} · ${llave.aula}` : `Slot ${slot}`}
          >
            {slot}
          </span>
        );
      })}
      <div className="carrusel-centro">
        <span className="suave chico">En el disco</span>
        <strong>{porSlot.size}</strong>
        <span className="suave chico">de {equipo.llaves.length} llaves</span>
      </div>
    </div>
  );
}

/** Una llave con su tag. El lapiz permite cambiar el UID (US-10). */
function FilaLlave({ llave, alGuardar }: { llave: LlaveEquipo; alGuardar: () => void }) {
  const { manejarError } = useSesion();
  const [editando, setEditando] = useState(false);
  const [uid, setUid] = useState(llave.rfidUid);
  const [error, setError] = useState<string | null>(null);
  const [guardando, setGuardando] = useState(false);

  async function guardar(e: FormEvent) {
    e.preventDefault();
    setGuardando(true);
    setError(null);
    try {
      await api.cambiarRfid(llave.id, uid);
      setEditando(false);
      alGuardar();
    } catch (err) {
      setError(manejarError(err)); // ej. "Este tag ya pertenece al aula 214."
    } finally {
      setGuardando(false);
    }
  }

  function cancelar() {
    setUid(llave.rfidUid);
    setError(null);
    setEditando(false);
  }

  return (
    <li>
      <div className="fila">
        <span className="mono col-aula">
          <strong>{llave.aula}</strong>
        </span>
        <span className="mono suave chico col-slot">
          {llave.slot === null ? '—' : `#${String(llave.slot).padStart(2, '0')}`}
        </span>
        {editando ? (
          <form className="fila crece" onSubmit={guardar}>
            <input
              autoFocus
              className="mono"
              aria-label={`UID del tag del aula ${llave.aula}`}
              value={uid}
              onChange={(e) => setUid(e.target.value.toUpperCase())}
            />
            <button type="submit" className="boton-texto" disabled={guardando} aria-label="Guardar UID">
              <Check size={18} />
            </button>
            <button type="button" className="boton-texto" onClick={cancelar} aria-label="Cancelar">
              <X size={18} />
            </button>
          </form>
        ) : (
          <>
            <span className="mono chico crece">{llave.rfidUid}</span>
            <Insignia estado={llave.estado} />
            <button
              type="button"
              className="boton-texto"
              onClick={() => setEditando(true)}
              aria-label={`Cambiar el tag del aula ${llave.aula}`}
            >
              <Pencil size={16} />
            </button>
          </>
        )}
      </div>
      {error && <p className="alerta alerta-error separado">{error}</p>}
    </li>
  );
}

/** "hace 12 s", "hace 3 min" o la hora si fue hace mucho */
function hace(fechaIso: string): string {
  const segundos = Math.max(0, Math.round((Date.now() - new Date(fechaIso).getTime()) / 1000));
  if (segundos < 60) return `hace ${segundos} s`;
  if (segundos < 3600) return `hace ${Math.floor(segundos / 60)} min`;
  return hora(fechaIso);
}
