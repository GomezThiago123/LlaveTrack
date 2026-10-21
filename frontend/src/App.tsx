// Pantallas de la web y sus direcciones
import { BrowserRouter, Navigate, Route, Routes } from 'react-router';
import Aulas from './paginas/Aulas';
import Cuenta from './paginas/Cuenta';
import Docentes from './paginas/Docentes';
import Equipo from './paginas/Equipo';
import Faltantes from './paginas/Faltantes';
import Historial from './paginas/Historial';
import Inicio from './paginas/Inicio';
import Login from './paginas/Login';
import MisLlaves from './paginas/MisLlaves';
import { PedirLink, Restablecer } from './paginas/Recuperar';
import { ProveedorSesion, RutaPreceptor, RutaPrivada } from './sesion';

export default function App() {
  return (
    <BrowserRouter>
      <ProveedorSesion>
        <Routes>
          {/* Sin login */}
          <Route path="/" element={<Inicio />} />
          <Route path="/login" element={<Login />} />
          <Route path="/recuperar" element={<PedirLink />} />
          <Route path="/restablecer" element={<Restablecer />} />

          {/* Con login: docentes, preceptores y admin */}
          <Route path="/aulas" element={<RutaPrivada><Aulas /></RutaPrivada>} />
          <Route path="/mis-llaves" element={<RutaPrivada><MisLlaves /></RutaPrivada>} />
          <Route path="/cuenta" element={<RutaPrivada><Cuenta /></RutaPrivada>} />
          {/* El codigo ahora se muestra arriba de las aulas */}
          <Route path="/codigo" element={<Navigate to="/aulas" replace />} />

          {/* Solo preceptor y admin */}
          <Route path="/faltantes" element={<RutaPreceptor><Faltantes /></RutaPreceptor>} />
          <Route path="/historial" element={<RutaPreceptor><Historial /></RutaPreceptor>} />
          <Route path="/equipo" element={<RutaPreceptor><Equipo /></RutaPreceptor>} />
          <Route path="/docentes" element={<RutaPreceptor><Docentes /></RutaPreceptor>} />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </ProveedorSesion>
    </BrowserRouter>
  );
}
