// Prepara el proyecto en una maquina nueva (Windows o Linux):
// 1. crea el entorno virtual de Python (.venv) si no existe
// 2. instala las dependencias de Python (requirements.txt)
// 3. instala las dependencias de Node (web)
// 4. copia server/.env.example a server/.env si no existe
import { spawnSync } from 'node:child_process';
import { copyFileSync, existsSync } from 'node:fs';
import path from 'node:path';

const raiz = path.resolve(import.meta.dirname, '..');
const enWindows = process.platform === 'win32';

function ejecutar(comando, args) {
  console.log(`\n> ${comando} ${args.join(' ')}`);
  // shell en Windows para que encuentre npm.cmd y py.exe
  const r = spawnSync(comando, args, { cwd: raiz, stdio: 'inherit', shell: enWindows });
  if (r.status !== 0) {
    console.error(`\nFallo: ${comando} ${args.join(' ')}`);
    process.exit(1);
  }
}

// Busca un Python 3.10 o mas nuevo instalado en el sistema
function buscarPython() {
  const candidatos = enWindows ? [['py', ['-3']], ['python', []]] : [['python3', []], ['python', []]];
  const chequeo = 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)';
  for (const [comando, args] of candidatos) {
    const r = spawnSync(comando, [...args, '-c', chequeo], { shell: enWindows });
    if (r.status === 0) return [comando, args];
  }
  console.error('No se encontro Python 3.10 o mas nuevo. Instalalo desde https://www.python.org');
  process.exit(1);
}

const venvPython = enWindows
  ? path.join(raiz, '.venv', 'Scripts', 'python.exe')
  : path.join(raiz, '.venv', 'bin', 'python');

if (!existsSync(venvPython)) {
  const [comando, args] = buscarPython();
  ejecutar(comando, [...args, '-m', 'venv', '.venv']);
}
ejecutar(venvPython, ['-m', 'pip', 'install', '-r', 'requirements.txt']);
ejecutar('npm', ['install']);

const env = path.join(raiz, 'server', '.env');
if (!existsSync(env)) {
  copyFileSync(path.join(raiz, 'server', '.env.example'), env);
  console.log('\nCreado server/.env a partir de server/.env.example');
}

console.log('\nListo. Para levantar todo: npm run dev');
