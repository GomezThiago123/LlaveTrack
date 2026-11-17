"""Genera arduino/llavesuba/llavesuba.ino: todo el firmware en un solo archivo, para grabarlo
con el Arduino IDE (sin PlatformIO).

El codigo de verdad sigue estando en src/ e include/: este script junta config.h, los .h y los
.cpp en un solo archivo y saca los #include entre ellos (quedan los de las librerias). Despues de
cambiar el firmware hay que volver a generarlo; si se edita el .ino a mano, el cambio se pierde.

Si existe include/secrets.h, lo copia al lado del .ino (esa copia no va al repo).

Uso, desde firmware/:  python generar_ino.py
"""

import re
import shutil
from pathlib import Path

AQUI = Path(__file__).resolve().parent
SALIDA = AQUI / "arduino" / "llavesuba"

ENCABEZADO = """\
// LlavesUBA: firmware del equipo en un solo archivo, para el Arduino IDE.
//
// NO EDITAR ESTE ARCHIVO: se genera con firmware/generar_ino.py a partir de firmware/src e
// include. Los cambios van en esos archivos y despues se vuelve a generar este.
//
// Para grabarlo con el Arduino IDE:
//   - Placa: "ESP32 Dev Module", con el paquete "esp32 by Espressif Systems" version 2.0.17
//     (Herramientas > Placa > Gestor de tarjetas). Es la que usa PlatformIO; con la 3.x no esta
//     probado.
//   - Partition Scheme: "Default 4MB with spiffs" (el programa ocupa ~1 MB de 1,2 MB).
//   - Librerias (Herramientas > Administrar bibliotecas), con estas versiones:
//       MFRC522 1.4.12 (GithubCommunity / miguelbalboa)
//       LiquidCrystal I2C 1.1.2 (Frank de Brabander)
//       Keypad 3.1.1 (Mark Stanley, Alexander Brevig)
//       PubSubClient 2.8 (Nick O'Leary)
//       ArduinoJson 7.4.2 (Benoit Blanchon)
//   - secrets.h (WiFi y broker) va en esta misma carpeta: es una copia de
//     firmware/include/secrets.h (ver secrets.example.h). Nunca se sube al repo.
//   - Monitor Serie: 115200 baudios y "Nueva linea".
"""

# Los .h primero (declaraciones), despues los .cpp; main.cpp al final (setup y loop)
def archivos_en_orden() -> list[Path]:
    src = AQUI / "src"
    cabeceras = sorted(src.glob("*.h"))
    fuentes = sorted(p for p in src.glob("*.cpp") if p.name != "main.cpp")
    return [AQUI / "include" / "config.h", *cabeceras, *fuentes, src / "main.cpp"]


# Un #include de un archivo del proyecto (no de una libreria). secrets.h se deja: va aparte
INCLUDE_LOCAL = re.compile(r'^\s*#include\s+"(?!secrets\.h)[^"]+"\s*$')


def limpiar(texto: str) -> str:
    """Saca los #pragma once y los #include del proyecto, y le pone sangria a lo que esta dentro
    del `namespace { ... }` de cada modulo (lo interno).

    La sangria es por el preprocesador de los .ino: inventa una declaracion para cada funcion que
    empieza en la columna 0 y las pone todas antes de la primera. Si esa primera es interna, las
    declaraciones quedan dentro del namespace de un modulo y no compila. Con sangria solo ve las
    funciones publicas (el Arduino IDE ademas saltea solo las que estan en un namespace).
    """
    lineas = []
    dentro = False
    for linea in texto.splitlines():
        if linea.strip() == "#pragma once" or INCLUDE_LOCAL.match(linea):
            continue
        if linea.startswith("namespace {"):
            dentro = True
        elif linea.startswith("}  // namespace"):
            dentro = False
        elif dentro and linea.strip():
            linea = "  " + linea
        lineas.append(linea)
    return "\n".join(lineas).strip("\n")


def main() -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    partes = [ENCABEZADO]
    for archivo in archivos_en_orden():
        nombre = archivo.relative_to(AQUI).as_posix()
        partes.append(f"\n// ===================== {nombre} =====================\n")
        partes.append(limpiar(archivo.read_text(encoding="utf-8")) + "\n")
    ino = SALIDA / "llavesuba.ino"
    ino.write_text("".join(partes), encoding="utf-8")
    print(f"Generado {ino.relative_to(AQUI)} ({sum(1 for _ in ino.open(encoding='utf-8'))} lineas)")

    secretos = AQUI / "include" / "secrets.h"
    if secretos.exists():
        shutil.copyfile(secretos, SALIDA / "secrets.h")
        print("Copiado include/secrets.h al lado del .ino (no va al repo)")
    else:
        print("Falta include/secrets.h: copia secrets.example.h, completalo y volve a generar")


if __name__ == "__main__":
    main()
