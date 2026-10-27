# Cableado del equipo

El cableado lo armaron los compañeros (27/10/2026). Esta tabla lo copia de su código de prueba; el firmware se adapta a estos pines.

Placa: NodeMCU ESP32 de 38 pines (ESP-WROOM-32).

## Pines

| Componente | Señal | GPIO | Nota |
| --- | --- | --- | --- |
| Lector RC522 | SCK | 18 | Bus SPI del ESP32 |
| | MISO | 19 | |
| | MOSI | 23 | |
| | SDA (SS) | 5 | |
| | RST | 27 | |
| LCD 16x2 (adaptador I2C) | SDA | 21 | Bus I2C del ESP32. Dirección: 0x27 o 0x3F (la muestra el programa de prueba) |
| | SCL | 22 | |
| Motor (L298N, canal B) | IN3 | 25 | Sentido de giro |
| | IN4 | 26 | Sentido de giro. ENB con jumper: siempre a velocidad máxima |
| Teclado 4x4 | Filas 1 a 4 | 4, 13, 14, 16 | Usan la resistencia interna del ESP32 |
| | Columnas 1 a 4 | 17, 32, 33, 2 | |
| LED bicolor | Verde | 12 | Con su resistencia |
| | Rojo | 15 | Los dos prendidos: amarillo o naranja |

## Alimentación

- Fuente 220 V → 16 V DC, con interruptor y fusible.
- Step-up a **24 V** para el motor, por el L298N. Al L298N se le saca el jumper de su regulador de 5 V y su lógica se alimenta con 5 V aparte.
- Step-down a **5 V** para el ESP32 (pin 5V o VIN) y el LCD.
- El RC522 va a **3,3 V**, desde el pin 3V3 del ESP32. **Nunca a 5 V.**
- **GND común** a todo.

## Cosas a tener en cuenta

- **GPIO 12 (LED verde)**: si está en alto cuando arranca el ESP32, la placa no prende. Con el LED y su resistencia hacia GND arranca bien; si alguna vez no arranca o no deja cargar el programa, desconectar ese LED es lo primero que hay que probar.
- **GPIO 2 y 15** también los mira el ESP32 al arrancar; con lo que tienen conectado arrancan bien.
- **Sin control de velocidad**: como ENB tiene el jumper, el motor siempre gira al máximo. Si hace falta frenar más preciso, se puede sacar el jumper y conectar ENB a un GPIO libre (por ejemplo, el 4 no: lo usa el teclado; habría que elegir uno libre).
- **Un solo LED bicolor**: el diseño pedía dos (conexión y faltantes). Con uno solo hay que decidir qué muestra cada color.
- Si el adaptador I2C del LCD va a 5 V, sus resistencias ponen 5 V en SDA y SCL del ESP32 (que es de 3,3 V): conviene un adaptador de nivel.

## Programa de prueba

`firmware/prueba_arduino/prueba_arduino.ino` (Arduino IDE) prueba cada parte con estos pines y mide cuánto tarda el disco en dar una vuelta (comando `v`).
