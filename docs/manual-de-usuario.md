# Manual de usuario de LlavesUBA

Cómo se usa el sistema día a día. Hay dos tipos de usuario: el **docente**, que retira y devuelve llaves, y el **preceptor**, que controla todo desde la web.

Para levantar el sistema en una compu: [README](../README.md). Para subirlo a la nube: [despliegue.md](despliegue.md).

## Para el docente

### Entrar a la web

1. Abrí la web desde el celular y entrá con tu **email y contraseña**.
2. **La primera vez:** el preceptor te da de alta y te llega un mail "LlavesUBA: creá tu contraseña". El link vence en 48 horas.
3. **Si te olvidaste la contraseña:** tocá "Olvidé mi contraseña" y te llega un link por mail. Vence en 30 minutos y sirve una sola vez.
4. **Por seguridad:**
   - la sesión se cierra sola después de 1 minuto sin usar la web;
   - si te equivocás de contraseña 5 veces seguidas, la cuenta se bloquea 15 minutos. El preceptor la puede desbloquear antes.

Sin entrar, la página principal muestra qué aulas están disponibles y si el equipo está conectado.

### Retirar una llave

1. **Parate frente al equipo.** La llave sale apenas la pedís.
2. En **Aulas**, buscá el aula. Si querés, completá **"Uso el aula hasta las"**: si 15 minutos después no la devolviste, te llega un mail para recordártelo.
3. Tocá **"Pedir llave"**. La web muestra *"El equipo está sacando tu llave"*, con una cuenta regresiva.
4. El disco gira. La pantalla del equipo dice "Hola Ana / Aula 214" y después "Aula 214 servida / RETIRE SU LLAVE".
5. **Sacá la llave de la ventana.** El equipo muestra "Gracias" y tu apellido, y el préstamo queda registrado a tu nombre con la hora.

Si no la sacás en un minuto, el equipo la vuelve a guardar. La reserva vence a los 2 minutos; mientras tanto la podés cancelar con **"Cancelar reserva"**.

"Pedir llave" no se puede tocar en estos casos:
- **el equipo está desconectado:** se habilita solo cuando vuelve;
- **ya tenés una reserva pendiente:** se puede tener una sola a la vez.

### Si te olvidaste el celular: con tu DNI

Funciona si el preceptor cargó tu DNI.

1. Apretá **A** en el teclado del equipo.
2. Escribí tu DNI (sin puntos) y apretá **#**.
3. Escribí el número de aula y apretá **#**.
4. Sigue igual que desde la web, desde el paso 4.

Si escribís 3 DNI que no son de nadie, el teclado se bloquea 30 segundos.

### Devolver una llave

1. Apretá **B** en el teclado. La pantalla dice "Cuelgue la llave".
2. Colgá la llave en el **lugar vacío** que está frente a la ventana.
3. El lector la reconoce solo: "Llave de aula 214 recibida". **No hace falta el celular ni apretar nada más.**

**Si devolvés la llave de otro docente:** después de **B**, escribí tu DNI y apretá **#**. La pantalla muestra "Retirada por Perez #=OK"; apretá **#** para confirmar. Queda registrado que la devolviste vos, y al otro docente le llega un mail.

**Si el equipo está sin conexión:** la devolución igual funciona. Se guarda en el equipo y se registra cuando vuelve la conexión, con la hora real.

### Mis llaves

En **Mis llaves** ves las llaves que tenés ahora y tus préstamos anteriores.

### Teclas del equipo

| Tecla | Qué hace |
| --- | --- |
| **A** | Retirar con DNI y aula (solo si no tenés el celular) |
| **B** | Devolver una llave |
| **C** | Cancelar |
| **\*** | Borrar el último número |
| **#** | Confirmar |

### Si algo sale mal

| La pantalla del equipo dice | Qué pasó y qué hacer |
| --- | --- |
| "Reposicionando / Espere..." | El disco no encontró tu llave al primer intento y la busca de nuevo. Esperá |
| "Pedi la llave / en porteria" | No la encontró ni con el segundo intento. Ya quedó avisado el preceptor: pedila en portería |
| "Llave no / reconocida" | La llave que colgaste no tiene un préstamo abierto, o no es del sistema. Sacala y avisá al preceptor |
| "Sin conexion" | El equipo no llega al servidor. No entrega llaves, pero sí recibe devoluciones |
| "Tiempo agotado" | Nadie sacó la llave en un minuto. El equipo la guardó; la reserva sigue hasta que vence |

## Para el preceptor

El preceptor tiene, abajo, **Aulas · Faltantes · Historial · Equipo · Docentes**, y arriba **Cuenta**.

| Pantalla | Qué se hace |
| --- | --- |
| **Aulas** | Ver todas las aulas y quién tiene cada llave, desde qué hora y su teléfono. Arriba aparecen los cuadros **"Incidentes del equipo"** (cuando el equipo no pudo entregar una llave: el aula queda "En revisión" hasta que se marca como resuelto) y **"Cuentas bloqueadas"**, con el botón para desbloquear |
| **Faltantes** | Las llaves que están fuera del disco, con el contacto del docente. **"Enviar recordatorio"** le manda un mail. Si el docente dijo hasta qué hora usaba el aula y pasó una hora, figura **"Demorada"** |
| **Historial** | Retiros y devoluciones filtrados por aula, docente, fechas y estado. Los préstamos sin devolver van en rojo. **"Exportar a Excel"** baja el mismo listado. Abajo, las **llaves dadas de baja** |
| **Equipo** | Si el equipo está en línea y qué llave hay en cada lugar del disco. **"Recalibrar el disco"** lo vuelve a ubicar. **"Dar de alta una llave (modo alta)"**: se acerca el tag nuevo al lector y se elige el aula. En la lista de tags: el **lápiz** cambia el tag de una llave y el **tacho** la da de baja si se perdió (pide el motivo); una llave de baja se repone con **"Reponer"** |
| **Docentes** | **Dar de alta** a un docente nuevo: le llega un mail para crear su contraseña. **Desactivar** o **Activar** cuentas, y **Cargar DNI** para que pueda retirar con el teclado |
