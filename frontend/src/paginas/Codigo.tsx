// El codigo para ingresar en el equipo, grande y con cuenta regresiva (US-03).
// Se puede recargar la pagina: el codigo se vuelve a pedir al servidor.
// Cada 5 s consulta la reserva para avisar cuando se retiro la llave, vencio o se cancelo.
import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router';
import { api, type Reserva } from '../api';
import { Alerta, Pagina } from '../componentes/Comunes';
import { useSesion } from '../sesion';
import { delAula, nombreAula, REFRESCO_MS, useIntervalo } from '../utiles';

export default function Codigo() {
  const { manejarError } = useSesion();
  const [reserva, setReserva] = useState<Reserva | null | undefined>(undefined); // undefined = cargando
  const [ahora, setAhora] = useState(Date.now());
  const [error, setError] = useState<string | null>(null);
  const [cancelando, setCancelando] = useState(false);
  const [equipoOnline, setEquipoOnline] = useState<boolean | null>(null);

  useEffect(() => {
    api
      .reservaActiva()
      .then(setReserva)
      .catch((err) => setError(manejarError(err)));
  }, [manejarError]);

  // Mientras esta pendiente, pregunta al servidor si cambio (ej. el equipo acepto el codigo)
  // y si el equipo sigue conectado (US-22: si se cae, la reserva sigue valiendo hasta que vence).
  // Este pedido NO va como automatico: renueva la sesion, para que no se cierre (60 s, US-01)
  // mientras el docente va al equipo. Deja de renovarla cuando la reserva se usa o vence.
  const actualizar = useCallback(() => {
    if (reserva?.estado !== 'PENDIENTE') return;
    api
      .reserva(reserva.id)
      .then(setReserva)
      .catch((err) => setError(manejarError(err)));
    api
      .estadoPublico(true)
      .then((estado) => setEquipoOnline(estado.equipoOnline))
      .catch(() => {}); // si falla, el pedido de la reserva ya muestra el error
  }, [reserva, manejarError]);

  useEffect(() => {
    api
      .estadoPublico()
      .then((estado) => setEquipoOnline(estado.equipoOnline))
      .catch(() => {});
  }, []);

  useIntervalo(actualizar, REFRESCO_MS);
  useIntervalo(() => setAhora(Date.now()), 1000); // para la cuenta regresiva

  async function cancelar() {
    if (!reserva || !window.confirm(`¿Cancelar la reserva de la llave ${delAula(reserva.aula)}?`)) return;
    setCancelando(true);
    try {
      await api.cancelarReserva(reserva.id);
      setReserva({ ...reserva, estado: 'CANCELADA' });
    } catch (err) {
      setError(manejarError(err));
    } finally {
      setCancelando(false);
    }
  }

  if (reserva === undefined) {
    return (
      <Pagina>
        <Alerta>{error}</Alerta>
        {!error && <p className="cargando">Cargando…</p>}
      </Pagina>
    );
  }

  if (reserva === null) {
    return (
      <Pagina>
        <h1>Mi código</h1>
        <p>No tenés ningún código activo.</p>
        <VolverAAulas texto="Pedir una llave" />
      </Pagina>
    );
  }

  const segundos = Math.max(0, Math.floor((new Date(reserva.expiraEn).getTime() - ahora) / 1000));
  // El servidor la pasa a VENCIDA en el proximo refresco; mientras, ya se muestra vencida
  const vencida = reserva.estado === 'VENCIDA' || (reserva.estado === 'PENDIENTE' && segundos === 0);

  if (reserva.estado === 'USADA') {
    return (
      <Pagina>
        <Alerta tipo="ok">Retiraste la llave {delAula(reserva.aula)}.</Alerta>
        <p>Acordate de devolverla en el equipo cuando termines: tecla B y colgala en el lugar vacío.</p>
        <VolverAAulas />
      </Pagina>
    );
  }

  if (reserva.estado === 'CANCELADA' || vencida) {
    return (
      <Pagina>
        <Alerta tipo="aviso">
          {vencida
            ? `El código para la llave ${delAula(reserva.aula)} venció.`
            : `Cancelaste la reserva de la llave ${delAula(reserva.aula)}.`}
        </Alerta>
        <VolverAAulas texto="Pedir una llave" />
      </Pagina>
    );
  }

  const minutos = Math.floor(segundos / 60);
  const resto = String(segundos % 60).padStart(2, '0');

  return (
    <Pagina>
      <h1>{nombreAula(reserva.aula)}</h1>
      {equipoOnline === false && (
        <Alerta tipo="aviso">
          El equipo está desconectado. Tu código sigue valiendo hasta que venza: si el equipo vuelve
          antes, lo vas a poder usar.
        </Alerta>
      )}
      <div className="codigo" aria-label={`Código ${reserva.codigo.split('').join(' ')}`}>
        {reserva.codigo.slice(0, 3)}&nbsp;{reserva.codigo.slice(3)}
      </div>
      <p className={`cuenta ${segundos < 60 ? 'cuenta-poco' : ''}`}>
        Vence en {minutos}:{resto}
      </p>

      <ol className="pasos">
        <li>
          En el equipo, tocá la tecla <kbd>A</kbd>.
        </li>
        <li>
          Ingresá el código y confirmá con <kbd>#</kbd>. Si te equivocás, <kbd>*</kbd> borra.
        </li>
        <li>Retirá la llave cuando aparezca en la ventana.</li>
      </ol>

      <Alerta>{error}</Alerta>
      <button type="button" className="boton boton-secundario boton-ancho" onClick={cancelar} disabled={cancelando}>
        {cancelando ? 'Cancelando…' : 'Cancelar reserva'}
      </button>
      <VolverAAulas />
    </Pagina>
  );
}

function VolverAAulas({ texto = 'Volver a las aulas' }: { texto?: string }) {
  return (
    <p className="centrado">
      <Link to="/aulas">{texto}</Link>
    </p>
  );
}
