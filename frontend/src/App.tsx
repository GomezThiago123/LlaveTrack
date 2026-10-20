// Pantallas de la web y sus direcciones
import { BrowserRouter, Navigate, Route, Routes } from 'react-router';
import Aulas from './paginas/Aulas';
import Codigo from './paginas/Codigo';
import Inicio from './paginas/Inicio';
import Login from './paginas/Login';
import { PedirLink, Restablecer } from './paginas/Recuperar';
import { ProveedorSesion, RutaPrivada } from './sesion';

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

          {/* Con login */}
          <Route path="/aulas" element={<RutaPrivada><Aulas /></RutaPrivada>} />
          <Route path="/codigo" element={<RutaPrivada><Codigo /></RutaPrivada>} />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </ProveedorSesion>
    </BrowserRouter>
  );
}
