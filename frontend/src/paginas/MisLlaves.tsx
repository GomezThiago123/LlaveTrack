// Mis llaves (US-17): las que tengo ahora y mis prestamos anteriores. Se actualiza cada 5 s,
// asi una llave devuelta desaparece de "En tu poder" en 5 segundos o menos.
import { api } from '../api';
import { Alerta, EtiquetaSeccion, PaginaApp } from '../componentes/Comunes';
import { TarjetaEnPoder } from '../componentes/Reserva';
import { useRefresco } from '../refresco';
import { duracion, fechaCorta, hora, nombreAula } from '../utiles';

export default function MisLlaves() {
  const { datos, error } = useRefresco((automatico) => api.misPrestamos(automatico));
  const enPoder = datos?.filter((p) => p.devueltoEn === null) ?? [];
  const anteriores = datos?.filter((p) => p.devueltoEn !== null) ?? [];

  return (
    <PaginaApp titulo="Mis llaves">
      <Alerta>{error}</Alerta>
      {!datos && !error && <p className="cargando">Cargando…</p>}

      {datos && (
        <>
          <EtiquetaSeccion>En tu poder</EtiquetaSeccion>
          {enPoder.length === 0 ? (
            <p className="tarjeta vacio">No tenés llaves en tu poder.</p>
          ) : (
            enPoder.map((p) => <TarjetaEnPoder key={p.id} aula={p.aula} desde={p.retiradoEn} />)
          )}

          <EtiquetaSeccion derecha={`${anteriores.length} registros`}>Mis préstamos</EtiquetaSeccion>
          {anteriores.length === 0 ? (
            <p className="vacio">Todavía no devolviste ninguna llave.</p>
          ) : (
            <ul className="lista">
              {anteriores.map((p) => (
                <li key={p.id} className="tarjeta fila">
                  <span className="cuadro-aula">{p.aula}</span>
                  <div className="crece">
                    <p>
                      <strong>{nombreAula(p.aula)}</strong> <span className="suave chico">· {fechaCorta(p.retiradoEn)}</span>
                    </p>
                    <p className="mono suave chico">
                      {hora(p.retiradoEn)} → {hora(p.devueltoEn!)}
                    </p>
                  </div>
                  <span className="mono suave chico">{duracion(p.retiradoEn, p.devueltoEn)}</span>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </PaginaApp>
  );
}
