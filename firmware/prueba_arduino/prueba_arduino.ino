// LlaveTrack: programa de PRUEBA del hardware (Arduino IDE). No es el firmware final.
//
// Prueba cada parte por separado y mide cuanto tarda el disco en dar una vuelta usando
// el tag HOME. Se maneja desde el Monitor Serie (115200 baudios, "Nueva linea").
//
// Comandos:
//   i  escanear el bus I2C (direccion del LCD: 0x27 o 0x3F)
//   l  probar el LED bicolor (verde, rojo y los dos juntos)
//   a  motor adelante      r  motor atras      s  parar el motor
//   v  medir vueltas: gira y muestra el tiempo entre pasadas del tag HOME (3 vueltas)
//   El lector RFID y el teclado se prueban solos: acerca un tag o toca una tecla.
//
// Librerias (Herramientas > Administrar bibliotecas):
//   MFRC522 (GithubCommunity / miguelbalboa), LiquidCrystal I2C (Frank de Brabander),
//   Keypad (Mark Stanley, Alexander Brevig).
// Placa: "ESP32 Dev Module".

#include <SPI.h>
#include <Wire.h>
#include <MFRC522.h>
#include <LiquidCrystal_I2C.h>
#include <Keypad.h>

// --- Pines: los del cableado que hicieron los companeros (ver docs/cableado.md) ---
const int RFID_SS = 5, RFID_RST = 27;         // SPI: SCK 18, MISO 19, MOSI 23
const int I2C_SDA = 21, I2C_SCL = 22;
const int MOTOR_IN3 = 25, MOTOR_IN4 = 26;     // canal B del L298N. ENB con jumper: siempre a velocidad maxima
const int LED_VERDE = 12, LED_ROJO = 15;      // un LED bicolor
byte FILAS[4] = {4, 13, 14, 16};
byte COLUMNAS[4] = {17, 32, 33, 2};

// --- Tags conocidos (leidos con NFC Tools el 27/10/2026) ---
const char *UID_HOME = "9A35EA81";
const char *TAGS[][2] = {
  {"9A35EA81", "HOME"}, {"A94B37A4", "101"}, {"2A86C880", "102"},
  {"5A81F281", "213"},  {"CAA8EA81", "214"}, {"2AC3FE80", "313"},
};

char TECLAS[4][4] = {
  {'1', '2', '3', 'A'},
  {'4', '5', '6', 'B'},
  {'7', '8', '9', 'C'},
  {'*', '0', '#', 'D'},
};

MFRC522 rfid(RFID_SS, RFID_RST);
LiquidCrystal_I2C *lcd = nullptr;  // se crea cuando el scanner encuentra la direccion
Keypad teclado = Keypad(makeKeymap(TECLAS), FILAS, COLUMNAS, 4, 4);

int sentido = 0;          // 1 adelante, -1 atras, 0 parado
bool midiendo = false;
unsigned long ultimaHome = 0;
int pasadasHome = 0;

// ---------------------------------------------------------------------------

void lcdMensaje(const String &linea1, const String &linea2) {
  if (!lcd) return;
  lcd->clear();
  lcd->setCursor(0, 0);
  lcd->print(linea1.substring(0, 16));  // el LCD tiene 16 caracteres por linea
  lcd->setCursor(0, 1);
  lcd->print(linea2.substring(0, 16));
}

byte escanearI2C() {
  byte encontrada = 0;
  Serial.println("Escaneando I2C...");
  for (byte dir = 1; dir < 127; dir++) {
    Wire.beginTransmission(dir);
    if (Wire.endTransmission() == 0) {
      Serial.printf("  Dispositivo en 0x%02X\n", dir);
      if (dir == 0x27 || dir == 0x3F) encontrada = dir;
    }
  }
  if (!encontrada) Serial.println("  No se encontro el LCD (0x27 ni 0x3F). Revisa SDA 21 / SCL 22 y la alimentacion.");
  return encontrada;
}

void motor(int nuevoSentido) {
  sentido = nuevoSentido;
  digitalWrite(MOTOR_IN3, sentido == 1 ? HIGH : LOW);
  digitalWrite(MOTOR_IN4, sentido == -1 ? HIGH : LOW);
  Serial.printf("Motor: %s\n", sentido == 1 ? "adelante" : sentido == -1 ? "atras" : "parado");
}

String uidLeido() {
  String uid = "";
  for (byte i = 0; i < rfid.uid.size; i++) {
    if (rfid.uid.uidByte[i] < 0x10) uid += "0";
    uid += String(rfid.uid.uidByte[i], HEX);
  }
  uid.toUpperCase();
  return uid;
}

const char *nombreDelTag(const String &uid) {
  for (auto &tag : TAGS) {
    if (uid == tag[0]) return tag[1];
  }
  return nullptr;
}

void probarLed() {
  Serial.println("LED verde (GPIO12)");
  digitalWrite(LED_VERDE, HIGH);
  delay(1000);
  digitalWrite(LED_VERDE, LOW);
  Serial.println("LED rojo (GPIO15)");
  digitalWrite(LED_ROJO, HIGH);
  delay(1000);
  digitalWrite(LED_ROJO, LOW);
  Serial.println("LED los dos juntos (se ve amarillo o naranja)");
  digitalWrite(LED_VERDE, HIGH);
  digitalWrite(LED_ROJO, HIGH);
  delay(1000);
  digitalWrite(LED_VERDE, LOW);
  digitalWrite(LED_ROJO, LOW);
}

void leerTag() {
  // IsNewCardPresent solo ve tags "nuevos": despues de leerlo se lo pone en HALT y no se
  // vuelve a ver hasta que sale del campo y vuelve a entrar. Asi cada pasada cuenta una vez.
  if (!rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial()) return;
  String uid = uidLeido();
  const char *nombre = nombreDelTag(uid);
  unsigned long ahora = millis();
  Serial.printf("Tag %s %s\n", uid.c_str(), nombre ? (String("= ") + nombre).c_str() : "(desconocido)");
  lcdMensaje(nombre ? String("Tag ") + nombre : "Tag desconocido", uid);

  if (midiendo && uid == UID_HOME && ahora - ultimaHome > 1000) {  // 1 s: ignora rebotes
    if (ultimaHome) {
      float segundos = (ahora - ultimaHome) / 1000.0;
      Serial.printf(">>> Vuelta %d: %.2f s (%.3f s por slot)\n", pasadasHome, segundos, segundos / 32);
    }
    ultimaHome = ahora;
    pasadasHome++;
    if (pasadasHome > 3) {
      motor(0);
      midiendo = false;
      Serial.println("Medicion terminada. Pasame los 3 tiempos.");
    }
  }
  rfid.PICC_HaltA();
}

// ---------------------------------------------------------------------------

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\nLlaveTrack: prueba de hardware");

  pinMode(MOTOR_IN3, OUTPUT);
  pinMode(MOTOR_IN4, OUTPUT);
  motor(0);
  pinMode(LED_VERDE, OUTPUT);
  pinMode(LED_ROJO, OUTPUT);
  digitalWrite(LED_VERDE, LOW);
  digitalWrite(LED_ROJO, LOW);

  Wire.begin(I2C_SDA, I2C_SCL);
  byte direccion = escanearI2C();
  if (direccion) {
    lcd = new LiquidCrystal_I2C(direccion, 16, 2);
    lcd->init();
    lcd->backlight();
    lcdMensaje("LlaveTrack", "Prueba hardware");
    Serial.printf("LCD en 0x%02X\n", direccion);
  }

  SPI.begin();
  rfid.PCD_Init();
  byte version = rfid.PCD_ReadRegister(MFRC522::VersionReg);
  if (version == 0x00 || version == 0xFF) {
    Serial.println("No responde el lector RC522: revisa cables y que este a 3,3 V.");
  } else {
    Serial.printf("Lector RC522 OK (version 0x%02X). Acerca un tag.\n", version);
  }
  Serial.println("Comandos: i l a r s v");
}

void loop() {
  leerTag();

  char tecla = teclado.getKey();
  if (tecla) {
    Serial.printf("Tecla: %c\n", tecla);
    lcdMensaje("Tecla:", String(tecla));
  }

  if (Serial.available()) {
    char c = Serial.read();
    switch (c) {
      case 'i': escanearI2C(); break;
      case 'l': probarLed(); break;
      case 'a': motor(1); break;
      case 'r': motor(-1); break;
      case 's': motor(0); midiendo = false; break;
      case 'v':
        Serial.println("Midiendo: gira hasta pasar 4 veces por HOME (3 vueltas). 's' para cortar.");
        midiendo = true;
        ultimaHome = 0;
        pasadasHome = 0;
        motor(1);
        break;
    }
  }
}
