// Mi cuenta: mis datos y cerrar sesion.
import { LogOut } from 'lucide-react';
import { PaginaApp } from '../componentes/Comunes';
import { useSesion } from '../sesion';
import { TEXTO_ROL } from '../utiles';

export default function Cuenta() {
  const { usuario, salir } = useSesion();
  if (!usuario) return null;
  const iniciales = `${usuario.nombre[0] ?? ''}${usuario.apellido[0] ?? ''}`.toUpperCase();

  return (
    <PaginaApp titulo="Mi cuenta">
      <section className="tarjeta fila fila-izquierda">
        <span className="cuadro-aula" aria-hidden>
          {iniciales}
        </span>
        <div>
          <p>
            <strong>
              {usuario.nombre} {usuario.apellido}
            </strong>
          </p>
          <p className="suave chico">{usuario.email}</p>
        </div>
      </section>
      <dl className="tarjeta datos">
        <div>
          <dt>Rol</dt>
          <dd>{TEXTO_ROL[usuario.rol]}</dd>
        </div>
        <div>
          <dt>Teléfono</dt>
          <dd>{usuario.telefono ?? '—'}</dd>
        </div>
      </dl>
      <button type="button" className="boton boton-peligro boton-ancho" onClick={salir}>
        <LogOut size={18} aria-hidden />
        Cerrar sesión
      </button>
    </PaginaApp>
  );
}
