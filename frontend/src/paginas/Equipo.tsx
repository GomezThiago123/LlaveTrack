// El equipo, para el preceptor: si esta conectado, que hay en cada slot del carrusel, los problemas
// de hoy (US-05) y el tag RFID de cada aula, que se puede cambiar (US-10). Se actualiza cada 5 s.
import { useState, type FormEvent } from 'react';
import { Check, Pencil, Trash2, X } from 'lucide-react';
import { api, type Equipo as DatosEquipo, type LlaveEquipo } from '../api';
import { Alerta, EtiquetaSeccion, Insignia, PaginaApp, PildoraEquipo } from '../componentes/Comunes';
import ProblemasEquipo from '../componentes/ProblemasEquipo';
import { useRefresco } from '../refresco';
import { useSesion } from '../sesion';
import { hora } from '../utiles';

// El equipo repite el homing (busca el tag HOME y mide la vuelta). Sirve para sacarlo de un error
// del disco ("Error del disco / Avisar porteria") sin desenchufarlo.
function Recalibrar({ online }: { online: boolean }) {
  const { manejarError } = useSesion();
  const [mensaje, setMensaje] = useState<{ tipo: 'ok' | 'error'; texto: string } | null>(null);
  const [mandando, setMandando] = useState(false);

  async function recalibrar() {
    if (!window.confirm('El disco va a dar una o dos vueltas para ubicarse. ¿Seguro?')) return;
    setMandando(true);
    setMensaje(null);
    try {
      await api.recalibrar();
      setMensaje({ tipo: 'ok', texto: 'Listo: el equipo está buscando el HOME (tarda hasta un minuto y medio).' });
    } catch (err) {
      setMensaje({ tipo: 'error', texto: manejarError(err) });
    } finally {
      setMandando(false);
    }
  }

  return (
    <>
      <button
        type="button"
        className="boton boton-claro boton-chico boton-ancho separado"
        onClick={recalibrar}
        disabled={!online || mandando}
      >
        Recalibrar el disco
      </button>
      {mensaje && <Alerta tipo={mensaje.tipo}>{mensaje.texto}</Alerta>}
    </>
  );
}

// US-10: el equipo deja un lugar vacio en la ventana y espera un tag. Lo que lee aparece aca
// (se actualiza cada 5 s): se elige el aula (una nueva o una con la llave de baja) y se guarda.
function ModoAlta({ equipo, alGuardar }: { equipo: DatosEquipo; alGuardar: () => void }) {
  const { manejarError } = useSesion();
  const [pedido, setPedido] = useState<number | null>(null); // cuando se pidio el modo alta
  const [aula, setAula] = useState('');
  const [mensaje, setMensaje] = useState<{ tipo: 'ok' | 'error'; texto: string } | null>(null);
  const tag = equipo.ultimoTag;
  // Solo cuenta un tag leido despues de apretar el boton
  const tagNuevo = tag && pedido !== null && new Date(tag.leidoEn).getTime() >= pedido ? tag : null;
  const sinLlave = equipo.llaves.filter((l) => l.estado === 'BAJA').map((l) => l.aula);

  async function empezar() {
    setMensaje(null);
    try {
      await api.modoAlta();
      setPedido(Date.now() - 2000);
      setMensaje({ tipo: 'ok', texto: 'El equipo espera el tag: acercalo al lector, en el lugar vacío de la ventana.' });
    } catch (err) {
      setMensaje({ tipo: 'error', texto: manejarError(err) });
    }
  }

  async function guardar(e: FormEvent) {
    e.preventDefault();
    if (!tagNuevo || tagNuevo.slot === null) return;
    try {
      await api.altaLlave({ aula: aula.trim(), rfidUid: tagNuevo.uid, slot: tagNuevo.slot });
      setMensaje({ tipo: 'ok', texto: `Listo: la llave del aula ${aula.trim()} quedó en el lugar ${tagNuevo.slot}.` });
      setPedido(null);
      setAula('');
      alGuardar();
    } catch (err) {
      setMensaje({ tipo: 'error', texto: manejarError(err) }); // ej. "Este tag ya pertenece al aula 214."
    }
  }

  return (
    <>
      <button
        type="button"
        className="boton boton-claro boton-chico boton-ancho separado"
        onClick={empezar}
        disabled={!equipo.online}
      >
        Dar de alta una llave (modo alta)
      </button>
      {mensaje && <Alerta tipo={mensaje.tipo}>{mensaje.texto}</Alerta>}
      {tagNuevo && (
        <form className="separado" onSubmit={guardar}>
          <p>
            Tag leído: <strong className="mono">{tagNuevo.uid}</strong>
            {tagNuevo.slot !== null && <span className="suave"> · lugar {tagNuevo.slot}</span>}
          </p>
          {tagNuevo.aula ? (
            <p className="alerta alerta-aviso">Este tag ya pertenece al aula {tagNuevo.aula}.</p>
          ) : (
            <div className="fila">
              <input
                className="crece"
                required
                list="aulas-sin-llave"
                placeholder="Aula (ej. 105)"
                aria-label="Aula de la llave"
                value={aula}
                onChange={(e) => setAula(e.target.value)}
              />
              <datalist id="aulas-sin-llave">
                {sinLlave.map((a) => (
                  <option key={a} value={a} />
                ))}
              </datalist>
              <button type="submit" className="boton boton-chico">
                Guardar
              </button>
            </div>
          )}
        </form>
      )}
    </>
  );
}

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
            <Recalibrar online={datos.online} />
            <ModoAlta equipo={datos} alGuardar={recargar} />
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
            Para dar de alta una llave nueva, usá el modo alta (arriba): el equipo lee el tag y lo muestra acá.
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

/** Una llave con su tag. El lapiz permite cambiar el UID (US-10); el tacho, darla de baja si se
 * perdio (US-11). Una llave de baja se repone con un tag nuevo y el lugar del disco donde se cuelga. */
function FilaLlave({ llave, alGuardar }: { llave: LlaveEquipo; alGuardar: () => void }) {
  const { manejarError } = useSesion();
  const deBaja = llave.estado === 'BAJA';
  const [editando, setEditando] = useState(false);
  const [uid, setUid] = useState(deBaja ? '' : llave.rfidUid);
  const [slot, setSlot] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [guardando, setGuardando] = useState(false);

  async function guardar(e: FormEvent) {
    e.preventDefault();
    setGuardando(true);
    setError(null);
    try {
      await api.cambiarRfid(llave.id, uid, slot === '' ? undefined : Number(slot));
      setEditando(false);
      alGuardar();
    } catch (err) {
      setError(manejarError(err)); // ej. "Este tag ya pertenece al aula 214."
    } finally {
      setGuardando(false);
    }
  }

  async function darDeBaja() {
    const motivo = window.prompt(`¿Por qué se da de baja la llave del aula ${llave.aula}? (ej. "Se perdió")`);
    if (!motivo) return;
    setError(null);
    try {
      await api.darDeBaja(llave.id, motivo);
      alGuardar();
    } catch (err) {
      setError(manejarError(err));
    }
  }

  function cancelar() {
    setUid(deBaja ? '' : llave.rfidUid);
    setSlot('');
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
              placeholder={deBaja ? 'UID del tag nuevo' : undefined}
              onChange={(e) => setUid(e.target.value.toUpperCase())}
            />
            {deBaja && (
              <input
                className="mono campo-slot"
                type="number"
                min={1}
                aria-label="Lugar del disco"
                placeholder="Slot"
                value={slot}
                onChange={(e) => setSlot(e.target.value)}
              />
            )}
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
            {deBaja ? (
              <button type="button" className="boton-texto chico" onClick={() => setEditando(true)}>
                Reponer
              </button>
            ) : (
              <>
                <button
                  type="button"
                  className="boton-texto"
                  onClick={() => setEditando(true)}
                  aria-label={`Cambiar el tag del aula ${llave.aula}`}
                >
                  <Pencil size={16} />
                </button>
                <button
                  type="button"
                  className="boton-texto"
                  onClick={darDeBaja}
                  aria-label={`Dar de baja la llave del aula ${llave.aula}`}
                  title="Dar de baja (se perdió)"
                >
                  <Trash2 size={16} />
                </button>
              </>
            )}
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
