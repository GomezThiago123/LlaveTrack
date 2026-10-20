// Docentes, para el preceptor: cuentas bloqueadas (US-07), dar de alta un docente y
// activarlo o desactivarlo (US-09). Un docente desactivado no puede iniciar sesion.
import { useState, type FormEvent } from 'react';
import { UserPlus } from 'lucide-react';
import { api, type UsuarioDetalle } from '../api';
import { Alerta, EtiquetaSeccion, Interruptor, PaginaApp } from '../componentes/Comunes';
import CuentasBloqueadas from '../componentes/CuentasBloqueadas';
import { useRefresco } from '../refresco';
import { useSesion } from '../sesion';
import { TEXTO_ROL } from '../utiles';

const VACIO = { nombre: '', apellido: '', email: '', telefono: '' };

export default function Docentes() {
  const { usuario } = useSesion();
  const usuarios = useRefresco((automatico) => api.usuarios(automatico));

  return (
    <PaginaApp titulo="Docentes">
      <CuentasBloqueadas />
      <FormularioAlta alCrear={() => usuarios.recargar()} />

      <Alerta>{usuarios.error}</Alerta>
      <EtiquetaSeccion derecha={usuarios.datos && `${usuarios.datos.length} usuarios`}>Usuarios</EtiquetaSeccion>
      {!usuarios.datos && !usuarios.error && <p className="cargando">Cargando…</p>}
      {usuarios.datos && (
        <ul className="tarjeta lista-divisiones">
          {usuarios.datos.map((u) => (
            <FilaUsuario key={u.id} usuario={u} esYo={u.id === usuario?.id} alCambiar={() => usuarios.recargar()} />
          ))}
        </ul>
      )}
    </PaginaApp>
  );
}

function FormularioAlta({ alCrear }: { alCrear: () => void }) {
  const { manejarError } = useSesion();
  const [abierto, setAbierto] = useState(false);
  const [datos, setDatos] = useState(VACIO);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [listo, setListo] = useState<string | null>(null);

  async function enviar(e: FormEvent) {
    e.preventDefault();
    setEnviando(true);
    setError(null);
    try {
      const nuevo = await api.altaDocente(datos);
      setListo(`Listo. Le mandamos un mail a ${nuevo.email} para que cree su contraseña.`);
      setDatos(VACIO);
      setAbierto(false);
      alCrear();
    } catch (err) {
      setError(manejarError(err)); // ej. "Ya hay un usuario cargado con ese email."
    } finally {
      setEnviando(false);
    }
  }

  const campo = (clave: keyof typeof VACIO) => ({
    value: datos[clave],
    onChange: (e: React.ChangeEvent<HTMLInputElement>) => setDatos({ ...datos, [clave]: e.target.value }),
  });

  if (!abierto) {
    return (
      <>
        <Alerta tipo="ok">{listo}</Alerta>
        <button
          type="button"
          className="boton boton-ancho"
          onClick={() => {
            setAbierto(true);
            setListo(null);
          }}
        >
          <UserPlus size={18} aria-hidden />
          Dar de alta un docente
        </button>
      </>
    );
  }

  return (
    <form className="tarjeta formulario" onSubmit={enviar}>
      <h2>Docente nuevo</h2>
      <div className="dos-columnas">
        <label>
          Nombre
          <input required autoComplete="off" {...campo('nombre')} />
        </label>
        <label>
          Apellido
          <input required autoComplete="off" {...campo('apellido')} />
        </label>
      </div>
      <label>
        Email
        <input type="email" required autoComplete="off" {...campo('email')} />
      </label>
      <label>
        Teléfono (opcional)
        <input type="tel" autoComplete="off" {...campo('telefono')} />
      </label>
      <p className="suave chico">Le llega un mail con un link para crear su contraseña (vence en 48 horas).</p>
      <Alerta>{error}</Alerta>
      <div className="dos-columnas">
        <button type="button" className="boton boton-claro" onClick={() => setAbierto(false)}>
          Cancelar
        </button>
        <button type="submit" className="boton" disabled={enviando}>
          {enviando ? 'Guardando…' : 'Dar de alta'}
        </button>
      </div>
    </form>
  );
}

function FilaUsuario({ usuario, esYo, alCambiar }: { usuario: UsuarioDetalle; esYo: boolean; alCambiar: () => void }) {
  const { manejarError } = useSesion();
  const [error, setError] = useState<string | null>(null);
  const [guardando, setGuardando] = useState(false);

  async function cambiar(activo: boolean) {
    const accion = activo ? 'activar' : 'desactivar';
    if (!window.confirm(`¿${accion[0].toUpperCase()}${accion.slice(1)} a ${usuario.nombre} ${usuario.apellido}?`)) return;
    setGuardando(true);
    setError(null);
    try {
      await api.cambiarActivo(usuario.id, activo);
      alCambiar();
    } catch (err) {
      setError(manejarError(err));
    } finally {
      setGuardando(false);
    }
  }

  return (
    <li>
      <div className="fila">
        <div className="crece">
          <p>
            <strong>
              {usuario.apellido}, {usuario.nombre}
            </strong>{' '}
            {esYo && <span className="suave chico">(vos)</span>}
          </p>
          <p className="suave chico">{usuario.email}</p>
          <p className="fila fila-izquierda separado">
            <span className="insignia insignia-neutra">{TEXTO_ROL[usuario.rol]}</span>
            {!usuario.activo && <span className="insignia insignia-prestada">Desactivado</span>}
            {usuario.activo && !usuario.tieneClave && (
              <span className="insignia insignia-reservada">Sin contraseña todavía</span>
            )}
          </p>
        </div>
        <Interruptor
          activo={usuario.activo}
          alCambiar={cambiar}
          deshabilitado={esYo || guardando}
          etiqueta={`${usuario.activo ? 'Desactivar' : 'Activar'} a ${usuario.nombre} ${usuario.apellido}`}
        />
      </div>
      {error && <p className="alerta alerta-error separado">{error}</p>}
    </li>
  );
}
