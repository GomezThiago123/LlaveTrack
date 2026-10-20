// Recuperar contraseña (US-08): pedir el link por mail y, con el link, elegir una nueva.
import { useState, type FormEvent } from 'react';
import { Link, useSearchParams } from 'react-router';
import { api, ErrorApi } from '../api';
import { Alerta, Pagina } from '../componentes/Comunes';

const CLAVE_MIN = 8;

function mensajeDe(err: unknown) {
  return err instanceof ErrorApi ? err.mensaje : 'Algo salió mal. Probá de nuevo.';
}

/** /recuperar: se ingresa el email y llega un link. */
export function PedirLink() {
  const [email, setEmail] = useState('');
  const [listo, setListo] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function enviar(e: FormEvent) {
    e.preventDefault();
    setEnviando(true);
    setError(null);
    try {
      setListo((await api.recuperar(email)).mensaje);
    } catch (err) {
      setError(mensajeDe(err));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Pagina>
      <h1>Recuperar contraseña</h1>
      {listo ? (
        <>
          <Alerta tipo="ok">{listo}</Alerta>
          <p>Revisá tu correo (también la carpeta de spam). El link vence en 30 minutos.</p>
        </>
      ) : (
        <form onSubmit={enviar} className="formulario">
          <p>Ingresá tu email y te enviamos un link para elegir una contraseña nueva.</p>
          <label>
            Email
            <input type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </label>
          <Alerta>{error}</Alerta>
          <button type="submit" className="boton boton-ancho" disabled={enviando}>
            {enviando ? 'Enviando…' : 'Mandarme el link'}
          </button>
        </form>
      )}
      <p className="centrado">
        <Link to="/login">Volver a ingresar</Link>
      </p>
    </Pagina>
  );
}

/** /restablecer?token=...: el link del mail lleva aca. */
export function Restablecer() {
  const [parametros] = useSearchParams();
  const token = parametros.get('token') ?? '';
  const [clave, setClave] = useState('');
  const [repetida, setRepetida] = useState('');
  const [listo, setListo] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function enviar(e: FormEvent) {
    e.preventDefault();
    if (clave !== repetida) {
      setError('Las contraseñas no coinciden.');
      return;
    }
    setEnviando(true);
    setError(null);
    try {
      await api.restablecer(token, clave);
      setListo(true);
    } catch (err) {
      setError(mensajeDe(err));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Pagina>
      <h1>Contraseña nueva</h1>
      {!token ? (
        <Alerta>El link está incompleto. Copialo entero desde el mail o pedí uno nuevo.</Alerta>
      ) : listo ? (
        <>
          <Alerta tipo="ok">Listo, ya cambiaste tu contraseña.</Alerta>
          <Link to="/login" className="boton boton-ancho">
            Ingresar
          </Link>
        </>
      ) : (
        <form onSubmit={enviar} className="formulario">
          <label>
            Contraseña nueva (mínimo {CLAVE_MIN} caracteres)
            <input
              type="password"
              autoComplete="new-password"
              required
              minLength={CLAVE_MIN}
              value={clave}
              onChange={(e) => setClave(e.target.value)}
            />
          </label>
          <label>
            Repetila
            <input
              type="password"
              autoComplete="new-password"
              required
              value={repetida}
              onChange={(e) => setRepetida(e.target.value)}
            />
          </label>
          <Alerta>{error}</Alerta>
          <button type="submit" className="boton boton-ancho" disabled={enviando}>
            {enviando ? 'Guardando…' : 'Guardar contraseña'}
          </button>
        </form>
      )}
      {!listo && (
        <p className="centrado">
          <Link to="/recuperar">Pedir un link nuevo</Link>
        </p>
      )}
    </Pagina>
  );
}
