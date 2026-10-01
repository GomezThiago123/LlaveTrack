// Ejecuta el Python del entorno virtual (.venv) con los argumentos recibidos.
// Existe porque la ruta del venv es distinta en Windows y en Linux.
// Ej.: node scripts/py.mjs -m pytest server
import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import path from 'node:path';

const raiz = path.resolve(import.meta.dirname, '..');
const python =
  process.platform === 'win32'
    ? path.join(raiz, '.venv', 'Scripts', 'python.exe')
    : path.join(raiz, '.venv', 'bin', 'python');

if (!existsSync(python)) {
  console.error('No existe el entorno virtual .venv. Corre primero: npm run setup');
  process.exit(1);
}

const resultado = spawnSync(python, process.argv.slice(2), { stdio: 'inherit' });
process.exit(resultado.status ?? 1);
