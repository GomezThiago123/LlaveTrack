# Pendientes de LlaveTrack

Última actualización: 20/10/2026. Hechas hasta ahora: Fase 0, Fase 1, Fase 2 (salvo Google) y US-20.

## 1. Respuestas que necesito de vos

Bloquean trabajo: sin estas respuestas no se puede seguir con lo que dice cada una.

- [ ] **Slots del disco y llaves para la demo.** Hoy son 24 slots con el 0 reservado para el tag HOME, así que entran 23 llaves, y las aulas reales son 30. *Bloquea: el seed con las aulas reales.*
- [ ] **Asterisco de la Aula 105.** ¿Qué significa? *Bloquea: el seed.*
- [ ] **Motor:** modelo, cantidad de cables, tensión nominal y reducción (mirar la etiqueta). En las fotos parece un motorreductor de 2 cables y no un paso a paso: si es así, hace falta un sensor que cuente las pestañas del disco. *Bloquea: la Fase 3 (motor).*
- [ ] **Modelo exacto de la placa ESP32.** *Bloquea: el mapa de pines.*
- [ ] **LCD:** confirmar que es 16x2 y su dirección I2C (0x27 o 0x3F). Se ve con el scanner de la Fase 3.
- [ ] **Referencia de cero:** qué sensor (final de carrera, óptico o hall) o el tag HOME provisorio.
- [ ] **LEDs (US-21 y US-22):** ¿uno bicolor o dos? ¿Qué colores? Los GPIO y las resistencias los propongo en la Fase 3 y los confirmás vos.
- [ ] **Servidor en la demo:** ¿notebook en la misma red o en la nube? ¿El WiFi de la escuela tiene portal cautivo o WPA2-Enterprise? Si tiene, hay que usar el router propio o un hotspot.

## 2. Lo próximo en el código

En el orden acordado. Cada uno arranca con un plan corto y espera tu OK.

- [ ] **US-21: LED y LCD de llaves faltantes.** Mi propuesta: el servidor publica `llavetrack/v1/{deviceId}/faltantes` (retenido) con `{"aulas":[...]}` cada vez que cambia la lista. En el simulador y en los tests.
- [ ] **US-22: LED de conexión con el servidor.** Mi propuesta: el servidor publica `llavetrack/v1/servidor/estado` (retenido, con su propio LWT). Falta decidir si el LED titila mientras reintenta.
- [ ] **Seed con las 30 aulas reales** (101–105, 111–115, 201–205, 211–215, 301–305, 311–315). Espera las respuestas de los slots y de la 105.
- [ ] **Documentación:** actualizar el CLAUDE.md y `docs/` con los tópicos nuevos, las variables de `.env` y los LEDs.

## 3. Web: lo que falta

- [ ] **Login con Google.** Hace falta crear el client ID en Google Cloud. Para usarlo desde celulares en la demo hace falta un dominio con HTTPS (deploy o túnel); si no hay, la demo usa contraseña.
- [ ] **Decidir qué parte del [prototipo](https://claude.ai/artifact/BUCVFTTa6UfGr5jqzBvFh5) pasa a la web real.** Candidatos: la grilla de aulas (con 30 aulas, la lista actual es larga), la barra de la cuenta regresiva y la confirmación de retiro.
- [ ] **Mail de recuperación de verdad para la demo:** completar `SMTP_*` en `backend/.env`, por ejemplo con Gmail y una contraseña de aplicación. Mientras tanto, el link sale en la consola del servidor.

## 4. Para probar vos

Ya están hechos, pero falta tu prueba.

- [ ] **Fase 2 en la compu:** pedir una llave como Ana, retirarla con el simulador y verla como Carla.
- [ ] **Fase 2 en el celular**, entrando a `http://<IP-de-la-compu>:5173`.
- [ ] **Sesión vencida:** con `SESION_MINUTOS=1` en `backend/.env`, la web vuelve sola al login.
- [ ] **US-20:** `desenchufar` y `enchufar` en el simulador; los botones de la web se deshabilitan y se habilitan solos.

## 5. Fase 3: firmware

Está bloqueada por las respuestas de hardware de la sección 1. Va un módulo por vez, cada uno con su programa de prueba:

- [ ] Proponer el mapa de pines (`config.h` y `docs/cableado.md`) y esperar tu confirmación.
- [ ] LCD y scanner I2C.
- [ ] Teclado 4x4.
- [ ] Lector RFID (RC522 a **3,3 V**).
- [ ] Motor, homing y calibración.
- [ ] WiFi y MQTT, con keepalive de 10 s, LWT retenido y latido cada 30 s (ver `docs/protocolo-mqtt.md`).
- [ ] LEDs de conexión y de faltantes.
- [ ] Máquina de estados completa y modo diagnóstico (tecla `D` al encender), que lista los UID reales para el seed.

## 6. Fase 4: integración y demo

- [ ] Probar con el equipo real y medir el tiempo de un ciclo completo de retiro y devolución.
- [ ] Mosquitto con usuario y contraseña por equipo, y una ACL que limite cada equipo a su prefijo.
- [ ] Cambiar las contraseñas de prueba del seed (`llavetrack`) antes de la demo.
- [ ] Si la web va por HTTPS, poner `COOKIE_SEGURA=true`.

## 7. Documentación de clase y defensa

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
