// La reserva del docente (US-03): el codigo en grande, la cuenta regresiva y como usarlo.
// Va arriba de la lista de aulas. Si se recarga la pagina, la lista la vuelve a pedir.
import { useState, type ReactNode } from 'react';
import { Clock, KeyRound, X } from 'lucide-react';
import { api, type Reserva } from '../api';
import { useSesion } from '../sesion';
import { delAula, hora, nombreAula, REFRESCO_MS, useIntervalo } from '../utiles';
import { Alerta } from './Comunes';

export function TarjetaReserva({
  reserva,
  alCambiar,
  equipoOnline,
}: {
  reserva: Reserva;
  alCambiar: (reserva: Reserva | null) => void;
  equipoOnline: boolean | null;
}) {
  const { manejarError } = useSesion();
  const [ahora, setAhora] = useState(Date.now());
  const [error, setError] = useState<string | null>(null);
  const [cancelando, setCancelando] = useState(false);

  // Mientras esta pendiente, pregunta si cambio (ej. ya se retiro la llave).
  // NO va como automatico: renueva la sesion, para que no se cierre (60 s, US-01) mientras el
  // docente va al equipo. Cuando la reserva se usa o vence, deja de preguntar.
  useIntervalo(() => {
    if (reserva.estado !== 'PENDIENTE') return;
    api
      .reserva(reserva.id)
      .then(alCambiar)
      .catch((err) => setError(manejarError(err)));
  }, REFRESCO_MS);
  useIntervalo(() => setAhora(Date.now()), 1000); // para la cuenta regresiva

  async function cancelar() {
    if (!window.confirm(`¿Cancelar la reserva de la llave ${delAula(reserva.aula)}?`)) return;
    setCancelando(true);
    try {
      await api.cancelarReserva(reserva.id);
      alCambiar({ ...reserva, estado: 'CANCELADA' });
    } catch (err) {
      setError(manejarError(err));
    } finally {
      setCancelando(false);
    }
  }

  const restanteMs = new Date(reserva.expiraEn).getTime() - ahora;
  const segundos = Math.max(0, Math.ceil(restanteMs / 1000));
  // El servidor la pasa a VENCIDA en el proximo pedido; mientras, ya se muestra vencida
  const vencida = reserva.estado === 'VENCIDA' || (reserva.estado === 'PENDIENTE' && segundos === 0);

  if (reserva.estado === 'USADA') {
    return (
      <Cerrable alCerrar={() => alCambiar(null)} tipo="ok">
        Retiraste la llave {delAula(reserva.aula)}. Devolvela en el equipo cuando termines: tecla <kbd>B</kbd>.
      </Cerrable>
    );
  }
  if (reserva.estado === 'CANCELADA' || vencida) {
    return (
      <Cerrable alCerrar={() => alCambiar(null)} tipo="aviso">
        {vencida
          ? `El código para la llave ${delAula(reserva.aula)} venció. La llave volvió a estar disponible.`
          : `Cancelaste la reserva de la llave ${delAula(reserva.aula)}.`}
      </Cerrable>
    );
  }

  // Cuanto queda del tiempo total (2 min, US-03; mas si el equipo ya acepto el codigo)
  const totalMs = new Date(reserva.expiraEn).getTime() - new Date(reserva.creadaEn).getTime();
  const fraccion = Math.max(0, Math.min(1, restanteMs / Math.max(totalMs, 1)));
  const poco = segundos < 30;
  const minutos = Math.floor(segundos / 60);
  const resto = String(segundos % 60).padStart(2, '0');

  return (
    <section className="reserva" aria-live="polite">
      <div className="fila">
        <p className="reserva-titulo">Tu código · {nombreAula(reserva.aula)}</p>
        <span className={`cuenta ${poco ? 'cuenta-poco' : ''}`}>
          <Clock size={14} aria-hidden />
          {minutos}:{resto}
        </span>
      </div>
      <div className="digitos" aria-label={`Código ${reserva.codigo.split('').join(' ')}`}>
        {reserva.codigo.split('').map((digito, i) => (
          <span key={i} aria-hidden>
            {digito}
          </span>
        ))}
      </div>
      <div className={`progreso ${poco ? 'progreso-poco' : ''}`} aria-hidden>
        <div style={{ width: `${fraccion * 100}%` }} />
      </div>
      {equipoOnline === false && (
        <Alerta tipo="aviso">El equipo está desconectado. El código sigue valiendo hasta que venza.</Alerta>
      )}
      <ol className="pasos">
        <li>
          En el equipo, tocá <kbd>A</kbd>.
        </li>
        <li>
          Ingresá el código y confirmá con <kbd>#</kbd> (<kbd>*</kbd> borra).
        </li>
        <li>Retirá la llave cuando aparezca en la ventana.</li>
      </ol>
      <Alerta>{error}</Alerta>
      <button type="button" className="boton boton-claro boton-ancho boton-chico" onClick={cancelar} disabled={cancelando}>
        <X size={16} aria-hidden />
        {cancelando ? 'Cancelando…' : 'Cancelar reserva'}
      </button>
    </section>
  );
}

function Cerrable({ tipo, alCerrar, children }: { tipo: 'ok' | 'aviso'; alCerrar: () => void; children: ReactNode }) {
  return (
    <div className={`alerta alerta-${tipo} fila`} role="status">
      <span>{children}</span>
      <button type="button" className="boton-texto" onClick={alCerrar} aria-label="Cerrar aviso">
        <X size={18} />
      </button>
    </div>
  );
}

/** "Tenés la llave del Aula 214" (US-17). Se devuelve en el equipo, no desde la app (US-06). */
export function TarjetaEnPoder({ aula, desde }: { aula: string; desde: string }) {
  return (
    <section className="en-poder">
      <div>
        <p className="reserva-titulo">En tu poder</p>
        <p>
          <strong>Tenés la llave {delAula(aula)}</strong>
        </p>
        <p className="suave chico">
          Retirada a las <span className="mono">{hora(desde)}</span>. Devolvela en el equipo: tecla <kbd>B</kbd> y
          colgala en el lugar vacío de la ventana.
        </p>
      </div>
      <span className="icono-llave" aria-hidden>
        <KeyRound size={20} />
      </span>
    </section>
  );
}
