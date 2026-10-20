// Login con email y contraseña (US-01). El bloqueo por intentos (US-07) lo decide el servidor.
import { useState, type FormEvent } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router';
import { api, ErrorApi } from '../api';
import { Alerta, Pagina } from '../componentes/Comunes';
import { useSesion } from '../sesion';

export default function Login() {
  const { usuario, ingresar, aviso } = useSesion();
  const navegar = useNavigate();
  const ubicacion = useLocation();
  const [email, setEmail] = useState('');
  const [clave, setClave] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  // A donde volver despues del login (si lo mando RutaPrivada), o la lista de aulas
  const destino = (ubicacion.state as { desde?: string } | null)?.desde ?? '/aulas';

  if (usuario) return <Navigate to={destino} replace />;

  async function enviar(e: FormEvent) {
    e.preventDefault();
    setEnviando(true);
    setError(null);
    try {
      ingresar(await api.login(email, clave));
      navegar(destino, { replace: true });
    } catch (err) {
      setError(err instanceof ErrorApi ? err.mensaje : 'Algo salió mal. Probá de nuevo.');
      setClave('');
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Pagina>
      <h1>Ingresar</h1>
      <Alerta tipo="aviso">{aviso}</Alerta>
      <form onSubmit={enviar} className="formulario">
        <label>
          Email
          <input
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>
        <label>
          Contraseña
          <input
            type="password"
            autoComplete="current-password"
            required
            value={clave}
            onChange={(e) => setClave(e.target.value)}
          />
        </label>
        <Alerta>{error}</Alerta>
        <button type="submit" className="boton boton-ancho" disabled={enviando}>
          {enviando ? 'Ingresando…' : 'Ingresar'}
        </button>
      </form>
      <p className="centrado">
        <Link to="/recuperar">Olvidé mi contraseña</Link>
      </p>
    </Pagina>
  );
}
