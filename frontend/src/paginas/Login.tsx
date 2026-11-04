// Login con email y contraseña (US-01). El bloqueo por intentos (US-07) lo decide el servidor.
import { useState, type FormEvent } from 'react';
import { Link, Navigate, useNavigate } from 'react-router';
import { ArrowRight, Eye, EyeOff } from 'lucide-react';
import { api, ErrorApi } from '../api';
import { Alerta, PaginaSimple } from '../componentes/Comunes';
import { useSesion } from '../sesion';

export default function Login() {
  const { usuario, ingresar, aviso } = useSesion();
  const navegar = useNavigate();
  const [email, setEmail] = useState('');
  const [clave, setClave] = useState('');
  const [verClave, setVerClave] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  // Despues del login siempre se arranca en Aulas, la pantalla principal (pedido de los
  // superiores, 05/11/2026)
  const destino = '/aulas';

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
    <PaginaSimple>
      <Alerta tipo="aviso">{aviso}</Alerta>
      <form onSubmit={enviar} className="tarjeta formulario">
        <label>
          Email
          <input type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label>
          <span className="fila">
            Contraseña
            <Link to="/recuperar" className="chico">
              ¿Olvidaste tu contraseña?
            </Link>
          </span>
          <span className="campo-clave">
            <input
              type={verClave ? 'text' : 'password'}
              autoComplete="current-password"
              required
              value={clave}
              onChange={(e) => setClave(e.target.value)}
            />
            <button type="button" onClick={() => setVerClave(!verClave)} aria-label={verClave ? 'Ocultar contraseña' : 'Mostrar contraseña'}>
              {verClave ? <EyeOff size={18} /> : <Eye size={18} />}
            </button>
          </span>
        </label>
        <Alerta>{error}</Alerta>
        <button type="submit" className="boton boton-ancho" disabled={enviando}>
          {enviando ? 'Ingresando…' : 'Ingresar'}
          {!enviando && <ArrowRight size={18} aria-hidden />}
        </button>
      </form>
      <p className="centrado chico">
        <Link to="/">Ver qué llaves hay sin ingresar</Link>
      </p>
    </PaginaSimple>
  );
}
