# User stories de LlaveTrack

Copiadas de Notion el 20/10/2026, tal cual están ahí. La numeración y el release (MVP / V2) son los de Notion.

> **Ojo con la numeración en los commits viejos:** hasta el 20/10/2026, en el código y en los commits se usaron "US-20", "US-21" y "US-22" para lo que hoy son **US-22, US-23 y US-24** (equipo conectado, llaves faltantes y conexión del equipo). Esas tres se cargaron en Notion el 20/10/2026; US-20 y US-21 son las de Notion (V2).

| US | Nombre | Release |
| --- | --- | --- |
| US-01 | Iniciar sesión | MVP |
| US-02 | Consultar aulas disponibles | MVP |
| US-03 | Solicitar la llave de un aula | MVP |
| US-04 | Retirar la llave | MVP |
| US-05 | Recibir siempre la llave correcta | MVP |
| US-06 | Devolver la llave | MVP |
| US-07 | Bloqueo por intentos fallidos | MVP |
| US-08 | Recuperar contraseña | MVP |
| US-09 | Registrar docentes | V2 |
| US-10 | Dar de alta una llave | V2 |
| US-11 | Dar de baja una llave perdida | V2 |
| US-12 | Historial de uso por aula | V2 |
| US-13 | Historial de uso por docente | V2 |
| US-14 | Devolver la llave sin conexión | V2 |
| US-15 | Corte de luz durante un retiro | V2 |
| US-16 | Recordatorio de devolución | V2 |
| US-17 | Ver mis llaves | V2 (story de referencia, 4 puntos) |
| US-18 | Retiro con credencial | V2 |
| US-19 | Exportar reportes | V2 |
| US-20 | Devolver una llave retirada por otro | V2 |
| US-21 | Registrar incidentes del equipo | V2 |
| US-22 | Ver si el equipo está conectado | MVP |
| US-23 | Ver en el equipo qué llaves faltan | MVP |
| US-24 | Ver en el equipo si está conectado | MVP |

---

## Épica: Acceso al sistema

### US-01 — Iniciar sesión (MVP)

**Como** profesor **deseo** ingresar con mi usuario y contraseña **para** que las llaves que retiro queden registradas a mi nombre.

**Criterios de aceptación**
- Dado que soy un docente activo, cuando ingreso usuario y contraseña correctos, entonces accedo a la pantalla de aulas y veo mi nombre arriba.
- Dado que ingreso una contraseña incorrecta, cuando confirmo, entonces veo "Usuario o contraseña incorrectos" (sin aclarar cuál de los dos falló).
- Si no hay actividad durante 60 segundos, la sesión se cierra sola.

**Para conversar:** ¿el login se hace desde el celular/web del docente o desde una pantalla del propio equipo?

## Épica: Retiro de llaves

### US-02 — Consultar aulas disponibles (MVP)

**Como** profesor **deseo** ver qué aulas están disponibles y cuáles ocupadas **para** saber qué llave puedo pedir sin ir hasta portería.

**Criterios de aceptación**
- Veo la lista de aulas con su estado: Disponible, Reservada u Ocupada.
- Si un aula está Ocupada, veo qué docente tiene la llave y desde qué hora.
- Cuando otro docente retira o devuelve una llave, el cambio se ve en 5 segundos o menos, sin recargar la página.

**Para conversar:** ¿todos los docentes pueden ver quién tiene cada llave, o solo el preceptor?

### US-03 — Solicitar la llave de un aula (MVP)

**Como** profesor **deseo** seleccionar el aula que necesito **para** que el sistema me prepare esa llave.

**Criterios de aceptación**
- Dado un aula Disponible, cuando la selecciono y confirmo, entonces queda Reservada a mi nombre.
- Dado que reservé un aula, cuando pasan 2 minutos sin retirar la llave, entonces la reserva se cancela y el aula vuelve a Disponible.
- Las aulas Ocupadas o Reservadas por otro docente no se pueden seleccionar.

### US-04 — Retirar la llave (MVP)

**Como** profesor **deseo** que el equipo me entregue la llave del aula que pedí **para** no depender de que alguien de portería me la alcance.

**Criterios de aceptación**
- Dado que realicé el pedido de una llave, cuando me acerco al equipo, entonces la llave de esa aula queda en la salida y el LCD muestra "Aula X servida - RETIRE SU LLAVE".
- Cuando el usuario retira la llave, confirmo en el LCD (muestra "Gracias X…"), se registra en el sistema el retiro con: docente, aula, fecha y hora, y el aula pasa a Ocupada.
- Si pasan más de X segundos y el usuario NO retira la llave, se debe informar la situación en la pantalla y se debe posicionar al equipo en un espacio sin llave (para evitar que la retire otra persona).

**Para conversar:** ¿cómo sabe el equipo qué docente se acercó? (código en pantalla, credencial, etc.)

### US-05 — Recibir siempre la llave correcta (MVP)

**Como** profesor **deseo** que el sistema compruebe que la llave entregada es la del aula que pedí **para** no terminar con la llave de otra aula.

**Criterios de aceptación**
- Antes de entregar la llave, el sistema lee su tag y lo compara con el aula reservada.
- Si coincide, el retiro sigue normalmente (US-04).
- Si no coincide, la llave no se entrega y el LCD muestra "Reposicionando..." mientras el equipo vuelve a intentar.
- Si falla 2 veces seguidas (el motor no gira, o la llave no está en el carrusel), el LCD muestra "Pedí la llave en portería" y queda registrado un incidente visible para el preceptor.

## Épica: Devolución de llaves

### US-06 — Devolver la llave (MVP)

**Como** profesor **deseo** colocar la llave en el equipo al terminar la clase **para** que quede registrado que la devolví y el aula se libere.

**Criterios de aceptación**
- Dado que tengo una llave retirada, cuando la coloco en el equipo, entonces el LCD muestra "Llave de aula X recibida".
- Cuando confirmo, se registra la devolución con fecha y hora y el aula pasa a Disponible.
- Al confirmar la recepción de la llave, se debe girar el carrusel a una posición vacía.
- Si coloco una llave desconocida o que no figura como retirada, el LCD muestra "Llave no reconocida" y no se registra nada.

**Para conversar:** ¿puede un docente devolver una llave que retiró otro?

## Épica: Seguridad y continuidad

### US-07 — Bloqueo por intentos fallidos (MVP)

**Como** preceptor **deseo** que una cuenta se bloquee después de varios intentos fallidos **para** que nadie retire llaves usando la cuenta de otro docente.

**Criterios de aceptación**
- Dado que alguien ingresa mal la contraseña de una cuenta 5 veces seguidas, entonces la cuenta queda bloqueada 15 minutos.
- Mientras está bloqueada, al intentar ingresar se ve "Cuenta bloqueada temporalmente".
- El preceptor puede desbloquearla manualmente antes de los 15 minutos.

### US-08 — Recuperar contraseña (MVP)

**Como** profesor **deseo** recuperar mi contraseña si me la olvido **para** poder retirar llaves sin pedirle ayuda al preceptor.

**Criterios de aceptación**
- Dado que olvidé mi contraseña, cuando ingreso mi email en "Olvidé mi contraseña", entonces recibo un email con un link para crear una nueva.
- El link vence a los 30 minutos y sirve una sola vez.
- Si el email no está registrado, se muestra el mismo mensaje: "Si el email está registrado, te enviamos un link".

## Épica: Gestión de inventario

### US-09 — Registrar docentes (V2)

**Como** preceptor **deseo** dar de alta a los docentes de la institución **para** que puedan usar el sistema.

**Criterios de aceptación**
- Cargo nombre, apellido y email; el docente recibe un email para crear su contraseña.
- No se pueden cargar dos docentes con el mismo email.
- Puedo desactivar a un docente; un docente desactivado no puede iniciar sesión.

### US-10 — Dar de alta una llave (V2)

**Como** preceptor **deseo** registrar una llave nueva y asociarla a un aula **para** que se pueda retirar desde el sistema.

**Criterios de aceptación**
- En modo alta, acerco el tag al lector, veo el ID leído, elijo el aula y guardo.
- Si el tag ya está registrado, veo "Este tag ya pertenece al aula X" y no se guarda.
- Después de guardar, el aula aparece como Disponible.

### US-11 — Dar de baja una llave perdida (V2)

**Como** preceptor **deseo** marcar una llave como perdida **para** que nadie intente retirarla y quede constancia de lo que pasó.

**Criterios de aceptación**
- Al marcarla como perdida cargo un motivo y la llave deja de aparecer para retiro.
- En el historial queda la baja con fecha, motivo y el último docente que la tuvo.
- Puedo reemplazarla asociando un tag nuevo a la misma aula (US-10).

## Épica: Historial y reportes

### US-12 — Historial de uso por aula (V2)

**Como** preceptor **deseo** ver todos los retiros y devoluciones de un aula **para** saber quién la usó y cuándo si hay algún problema.

**Criterios de aceptación**
- Filtro por aula y rango de fechas y veo: docente, hora de retiro, hora de devolución y duración.
- Los retiros sin devolución aparecen resaltados en rojo.
- Si no hay movimientos, veo "No hay movimientos para este período".

### US-13 — Historial de uso por docente (V2)

**Como** preceptor **deseo** ver los movimientos de llaves de un docente **para** controlar quién tiene llaves sin devolver.

**Criterios de aceptación**
- Filtro por docente y rango de fechas y veo: aula, hora de retiro, hora de devolución y duración.
- Arriba de la tabla veo cuántas llaves tiene hoy en su poder.
- Los retiros sin devolución aparecen resaltados en rojo.

### US-14 — Devolver la llave sin conexión (V2)

**Como** profesor **deseo** poder devolver la llave aunque se caiga el WiFi de la escuela **para** no quedarme con la llave encima.

**Criterios de aceptación**
- Si no hay conexión, el LCD muestra "Sin conexión".
- Sin conexión, la devolución se guarda en el equipo y se sincroniza al volver la conexión, con la hora real en que devolví.
- Mientras no hay conexión, el aula figura como Ocupada hasta que se sincroniza.

**Para conversar:** ¿los retiros sin conexión se bloquean o se permiten y se sincronizan después?

**Para conversar:** guardar en memoria NO volátil la llave devuelta e (idealmente) la hora de devolución (analizar necesidad de RTC).

### US-15 — Corte de luz durante un retiro (V2)

**Como** profesor **deseo** que un corte de luz a mitad de un retiro no deje registros erróneos **para** que no figure a mi nombre una llave que nunca recibí.

**Criterios de aceptación**
- Si se corta la luz antes de confirmar el retiro, al volver no queda registrado ningún retiro.
- Al volver la luz, el equipo regresa a su posición inicial y el LCD muestra "Equipo listo".
- La reserva que estaba activa se cancela y el aula vuelve a Disponible.

**Para conversar:** ¿en qué momento suponés que se corta la luz? ¿qué sucede si se corta la luz luego de que el carrusel sirvió la llave pero antes de que confirme el retiro y el usuario retira la llave igual?

### US-16 — Recordatorio de devolución (V2)

**Como** profesor **deseo** recibir un aviso si no devolví la llave al terminar mi turno **para** no llevármela a mi casa por olvido.

**Criterios de aceptación**
- Dado que tengo una llave retirada, cuando pasan 15 minutos del horario de fin de mi turno sin devolverla, entonces recibo un email con el aviso "Todavía tenés la llave del Aula X".
- Si devuelvo la llave antes de esos 15 minutos, no recibo ningún aviso.
- Si a los 60 minutos sigo sin devolverla, el preceptor ve la llave marcada como "Demorada".

**Para conversar:** ¿de dónde saca el sistema el horario de fin de turno de cada docente?

### US-17 — Ver mis llaves (V2)

**Como** profesor **deseo** ver qué llaves tengo en mi poder en este momento **para** saber cuáles me falta devolver.

**Criterios de aceptación**
- En la sección "Mis llaves" veo cada llave que tengo retirada con el aula y la hora de retiro.
- Si no tengo ninguna llave retirada, veo el mensaje "No tenés llaves en tu poder".
- Cuando devuelvo una llave, desaparece de la lista en 5 segundos o menos.

### US-18 — Retiro con credencial (V2)

**Como** profesor **deseo** identificarme en el equipo acercando mi credencial **para** retirar la llave sin tener que escribir usuario y contraseña.

**Criterios de aceptación**
- Dado que tengo una reserva activa, cuando acerco mi credencial al lector del equipo, entonces el LCD muestra "Hola [nombre] - Aula X" y sigue el retiro normal (US-04).
- Si acerco una credencial no registrada, el LCD muestra "Credencial no reconocida" y no se entrega ninguna llave.
- Si el preceptor desactivó mi cuenta (US-09), mi credencial deja de funcionar.

**Para conversar:** ¿la credencial la entrega la escuela o se usa una que los docentes ya tienen?

### US-19 — Exportar reportes (V2)

**Como** preceptor **deseo** descargar los historiales de uso en Excel **para** compartirlos con dirección o guardarlos fuera del sistema.

**Criterios de aceptación**
- En los historiales por aula (US-12) y por docente (US-13) hay un botón "Exportar a Excel".
- El archivo descargado tiene las mismas columnas y filtros que estoy viendo en pantalla.
- Si no hay movimientos en el período elegido, el botón aparece deshabilitado.

### US-20 — Devolver una llave retirada por otro (V2)

**Como** profesor **deseo** que me avisen cuando otro docente devuelve una llave que yo retiré **para** saber quién la tenía y quedarme tranquilo de que ya no figura a mi nombre.

**Criterios de aceptación**
- Dado que la llave del Aula X figura retirada por el docente A, cuando el docente B se identifica en el equipo y coloca la llave, entonces el LCD muestra "Aula X - Retirada por [docente A] - Confirmar devolución".
- Cuando el docente B confirma, se registra la devolución con fecha, hora, quién la había retirado y quién la devolvió, y el aula pasa a Disponible.
- En ese momento, el docente A recibe una notificación en la app y un email: "Tu llave del Aula X fue devuelta por [docente B] a las [hora]".
- La llave desaparece de "Mis llaves" del docente A (US-17).
- En el historial (US-12 y US-13), el preceptor ve esa devolución marcada como "Devuelta por terceros", con el nombre de quien la devolvió.
- Si quien devuelve no se identifica, el LCD muestra "Identificate para devolver una llave que no retiraste" y no se registra la devolución.

### US-21 — Registrar incidentes del equipo (V2)

**Como** preceptor **deseo** que quede registrado un incidente cuando el equipo no puede entregar una llave **para** saber qué falló, entregar la llave a mano y pedir que revisen el equipo.

**Criterios de aceptación**
- Dado que un docente tiene una reserva activa, cuando el equipo falla 2 veces seguidas (el motor no gira o la llave no está en el carrusel), entonces el LCD muestra "Pedí la llave en portería".
- Se registra un incidente con fecha, hora, aula, docente y tipo de falla ("Motor no gira" o "Llave no encontrada").
- En la sección "Incidentes", el preceptor ve los incidentes abiertos, del más reciente al más antiguo.
- Mientras el incidente esté abierto, esa aula no se puede reservar desde la app y figura como "En revisión".
- El preceptor puede marcar el incidente como "Resuelto" y el aula vuelve a Disponible.

## Agregadas el 20/10/2026 (ya construidas en el servidor y el simulador)

### US-22 — Ver si el equipo está conectado (MVP)

**Como** profesor **deseo** saber desde la web si el equipo está conectado **para** no ir hasta el equipo cuando no me puede entregar la llave.

**Criterios de aceptación**
- Si el equipo está desconectado, la web muestra "El equipo está desconectado" y el botón "Pedir llave" queda deshabilitado con el texto "Equipo desconectado".
- Cuando el equipo vuelve a conectarse, el botón se habilita solo en 5 segundos o menos, sin recargar la página.
- El equipo se considera desconectado si pierde la conexión (se detecta en unos 15 segundos) o si pasan 90 segundos sin ningún mensaje suyo.
- Si el equipo se desconecta con una reserva pendiente, la reserva no se cancela: sigue vigente hasta que vence.

### US-23 — Ver en el equipo qué llaves faltan (MVP)

**Como** preceptor **deseo** que el equipo muestre qué llaves no están en el carrusel **para** saber de un vistazo qué aulas siguen sin devolver.

**Criterios de aceptación**
- Mientras haya llaves retiradas sin devolver, el LED de faltantes del equipo está prendido; si no falta ninguna, está apagado.
- En reposo, la primera línea del LCD alterna entre la hora y "Faltan: 105 114" con las aulas cuyas llaves no están.
- Las llaves reservadas que todavía no se retiraron no cuentan como faltantes (siguen en el carrusel).
- Cuando se retira o se devuelve una llave, el equipo actualiza el LED y el LCD enseguida.

### US-24 — Ver en el equipo si está conectado (MVP)

**Como** profesor **deseo** ver en el equipo si está conectado con el sistema **para** saber si puedo retirar o devolver una llave.

**Criterios de aceptación**
- Si el equipo tiene WiFi y está conectado con el servidor, el LED de conexión queda fijo.
- Si falta algo, el LED titila y el LCD muestra "Sin conexion" con la causa: WiFi, Broker o Servidor.
- Sin conexión, el equipo no entrega ni recibe llaves.
- Cuando vuelve la conexión, el LED queda fijo y el equipo vuelve a funcionar solo.
