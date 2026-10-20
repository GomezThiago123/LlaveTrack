# Pendientes de LlaveTrack

Última actualización: 20/10/2026 (con tus respuestas de hardware). Hechas hasta ahora: Fase 0, Fase 1, Fase 2 (salvo Google) y US-20.

## 1. Respuestas que necesito de vos

Bloquean trabajo: sin estas respuestas no se puede seguir con lo que dice cada una.

- [ ] **Motor:** modelo, cantidad de cables, tensión nominal y reducción (mirar la etiqueta). En las fotos parece un motorreductor de 2 cables y no un paso a paso: si es así, hace falta un sensor que cuente las pestañas del disco. *Bloquea: la Fase 3 (motor).*
- [ ] **LEDs (US-21 y US-22):** ¿uno bicolor o dos? ¿Qué colores? Se decide en la Fase 3: ahí propongo GPIO y resistencias y los confirmás vos.
- [ ] **Proveedor de la nube** para el servidor (ver la sección 3). Lo propongo yo cuando lleguemos.
- [ ] **WiFi de la escuela:** aunque el servidor esté en la nube, el ESP32 tiene que salir a internet. ¿Tiene portal cautivo o WPA2-Enterprise? Si tiene, hay que usar el router propio o un hotspot.

### Ya respondidas (20/10/2026)

- **Disco:** 32 slots. El 0 es del tag HOME, así que quedan 31 lugares: entran las 30 aulas y sobra 1.
- **Aula 105:** el asterisco era un error; es un aula como las demás.
- **Placa:** NodeMCU ESP32 de 38 pines con USB-C (módulo ESP-WROOM-32).
- **LCD:** 16x2. La dirección I2C sale del scanner en la Fase 3.
- **Referencia de cero:** el tag RFID HOME en el slot 0, por ahora.
- **Servidor de la demo:** en la nube.

## 2. Lo próximo en el código

En el orden acordado. Cada uno arranca con un plan corto y espera tu OK.

- [x] **US-21: LED y LCD de llaves faltantes.** Hecho en el servidor y el simulador; en el equipo se hace en la Fase 3.
- [ ] **US-22: LED de conexión con el servidor.** Mi propuesta: el servidor publica `llavetrack/v1/servidor/estado` (retenido, con su propio LWT). Falta decidir si el LED titila mientras reintenta.
- [ ] **Seed con las 30 aulas reales** (101–105, 111–115, 201–205, 211–215, 301–305, 311–315), ya desbloqueado: `slotsTotales: 32`, slot 0 reservado para HOME y las aulas en los slots 1 a 30 (UID inventados hasta el modo diagnóstico). El simulador pasa a `--slots 32` por defecto.
- [ ] **Documentación:** actualizar el CLAUDE.md y `docs/` con los tópicos nuevos, las variables de `.env` y los LEDs.

## 3. El servidor en la nube

Como la demo corre en la nube, hay cosas nuevas para resolver antes de la Fase 4:

- [ ] **Elegir proveedor:** tiene que poder correr el servidor de Python **y** Mosquitto, que necesita un puerto TCP propio. Los hostings que solo sirven páginas web no alcanzan.
- [ ] **Dominio con HTTPS** para la web y la API.
- [ ] **Mosquitto expuesto a internet:** TLS en el puerto 8883, usuario y contraseña por equipo y una ACL por prefijo. Nunca el 1883 abierto. El ESP32 se conecta con `WiFiClientSecure` y el certificado raíz.
- [ ] **Base persistente:** SQLite en un disco que no se borre al reiniciar, o pasar a PostgreSQL (el proyecto ya está preparado con SQLAlchemy + Alembic).
- [ ] **Configurar el `.env` de producción:** `COOKIE_SEGURA=true`, `WEB_URL` con el dominio y `SMTP_*`.

## 4. Web: lo que falta

- [ ] **Login con Google.** Hace falta crear el client ID en Google Cloud. Ahora que va a haber un dominio con HTTPS, funciona también desde los celulares.
- [ ] **Decidir qué parte del [prototipo](https://claude.ai/artifact/BUCVFTTa6UfGr5jqzBvFh5) pasa a la web real.** Candidatos: la grilla de aulas (con 30 aulas, la lista actual es larga), la barra de la cuenta regresiva y la confirmación de retiro.
- [ ] **Mail de recuperación de verdad:** completar `SMTP_*`, por ejemplo con Gmail y una contraseña de aplicación. Mientras tanto, el link sale en la consola del servidor.

## 5. Para probar vos

Ya están hechos, pero falta tu prueba.

- [ ] **Fase 2 en la compu:** pedir una llave como Ana, retirarla con el simulador y verla como Carla.
- [ ] **Fase 2 en el celular**, entrando a `http://<IP-de-la-compu>:5173`.
- [ ] **Sesión vencida:** con `SESION_MINUTOS=1` en `backend/.env`, la web vuelve sola al login.
- [ ] **US-20:** `desenchufar` y `enchufar` en el simulador; los botones de la web se deshabilitan y se habilitan solos.

## 6. Fase 3: firmware

Lo único que falta del hardware es el motor (sección 1); lo demás ya se puede arrancar. Va un módulo por vez, cada uno con su programa de prueba:

- [ ] Proponer el mapa de pines para la NodeMCU ESP32 de 38 pines (`config.h` y `docs/cableado.md`) y esperar tu confirmación.
- [ ] LCD y scanner I2C.
- [ ] Teclado 4x4.
- [ ] Lector RFID (RC522 a **3,3 V**).
- [ ] Motor, homing y calibración.
- [ ] WiFi y MQTT, con keepalive de 10 s, LWT retenido y latido cada 30 s (ver `docs/protocolo-mqtt.md`).
- [ ] LEDs de conexión y de faltantes.
- [ ] Máquina de estados completa y modo diagnóstico (tecla `D` al encender), que lista los UID reales para el seed.

## 7. Fase 4: integración y demo

- [ ] Probar con el equipo real y medir el tiempo de un ciclo completo de retiro y devolución.
- [ ] Cambiar las contraseñas de prueba del seed (`llavetrack`) antes de la demo.

## 8. Documentación de clase y defensa

Estos documentos los presentaste en clase y no coinciden con lo que está construido.

- [ ] **CU-01:** el sistema usa código de **6 dígitos** que vence a los **10 min** (el documento dice 4 dígitos y 5 min). La devolución **no se pide desde la app**: se toca `B` en el equipo y se cuelga la llave. El ESP32 no consulta solicitudes cada 2 s: el código lo valida el servidor por MQTT.
- [ ] **Documentos de "Servicios", "Vinculación del ESP32" y "Base de datos":** describen Supabase (API REST, polling, heartbeat por HTTP, RLS). Lo construido es FastAPI + SQLite + Mosquitto. Hay que actualizarlos o explicar el cambio en la defensa.
- [ ] **Diagrama de bloques:**
  - Corregir "Relugador" por "Regulador".
  - Hoy el celular va directo a la Base de Datos: tiene que ir al Servidor, porque la web nunca toca la base.
  - Agregar el broker MQTT entre el ESP32 y el servidor, y los dos LEDs.
- [ ] **Caso de uso del administrador** ("¿quién se olvidó de devolver la llave X?"): en el MVP lo resuelve la lista de aulas del preceptor (quién la tiene, desde qué hora y su teléfono). La pantalla dedicada de "sin devolver" es V2.

## Fuera del MVP (V2)

No se hace salvo que lo pidas. La lista completa está en `CLAUDE.md`: historial (US-12/13), recordatorio de devolución (US-16), devolución sin conexión (US-14), altas y bajas desde la web (US-09/10/11), entre otras.
