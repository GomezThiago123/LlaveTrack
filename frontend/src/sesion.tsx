// Quien esta logueado, compartido por toda la web (Context de React).
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router';
import { api, ErrorApi, type Usuario } from './api';

interface Sesion {
  usuario: Usuario | null;
  cargando: boolean; // true mientras se pregunta al servidor si hay una sesion abierta
  aviso: string | null; // ej. "Tu sesion vencio", para mostrar en el login
  ingresar: (usuario: Usuario) => void;
  salir: () => Promise<void>;
  /** Llamarla cuando un pedido da error: si es 401 (sesion vencida) vuelve al login. */
  manejarError: (error: unknown) => string;
}

const ContextoSesion = createContext<Sesion | null>(null);

export function ProveedorSesion({ children }: { children: ReactNode }) {
  const [usuario, setUsuario] = useState<Usuario | null>(null);
  const [cargando, setCargando] = useState(true);
  const [aviso, setAviso] = useState<string | null>(null);

  // Al abrir la web: si la cookie de sesion sigue valida, el servidor devuelve el usuario
  useEffect(() => {
    api
      .yo()
      .then(setUsuario)
      .catch(() => setUsuario(null))
      .finally(() => setCargando(false));
  }, []);

  const ingresar = useCallback((u: Usuario) => {
    setAviso(null);
    setUsuario(u);
  }, []);

  const salir = useCallback(async () => {
    await api.logout().catch(() => {});
    setUsuario(null);
  }, []);

  const manejarError = useCallback((error: unknown) => {
    if (error instanceof ErrorApi && error.status === 401) {
      setAviso(error.mensaje);
      setUsuario(null); // RutaPrivada lo manda al login
    }
    return error instanceof ErrorApi ? error.mensaje : 'Algo salió mal. Probá de nuevo.';
  }, []);

  return (
    <ContextoSesion.Provider value={{ usuario, cargando, aviso, ingresar, salir, manejarError }}>
      {children}
    </ContextoSesion.Provider>
  );
}

export function useSesion(): Sesion {
  const sesion = useContext(ContextoSesion);
  if (!sesion) throw new Error('useSesion tiene que usarse dentro de <ProveedorSesion>');
  return sesion;
}

/** Pantallas que necesitan login: sin sesion, redirige a /login. */
export function RutaPrivada({ children }: { children: ReactNode }) {
  const { usuario, cargando } = useSesion();
  const ubicacion = useLocation();
  if (cargando) return <p className="cargando">Cargando…</p>;
  if (!usuario) return <Navigate to="/login" replace state={{ desde: ubicacion.pathname }} />;
  return <>{children}</>;
}
