#include "rfid.h"

#include <MFRC522.h>
#include <SPI.h>

#include "config.h"

namespace {
MFRC522 lector(PIN_RFID_SS, PIN_RFID_RST);

String uidActual() {
  String uid = "";
  for (byte i = 0; i < lector.uid.size; i++) {
    if (lector.uid.uidByte[i] < 0x10) uid += "0";
    uid += String(lector.uid.uidByte[i], HEX);
  }
  uid.toUpperCase();
  return uid;
}
}  // namespace

bool rfidIniciar() {
  SPI.begin();
  lector.PCD_Init();
  byte version = lector.PCD_ReadRegister(MFRC522::VersionReg);
  bool ok = version != 0x00 && version != 0xFF;
  Serial.printf("[rfid] %s (version 0x%02X)\n", ok ? "Lector OK" : "El lector NO responde: revisar cables y 3,3 V", version);
  return ok;
}

int rfidLeerTodos(String uids[], int maximo) {
  int leidos = 0;
  // 1) WUPA despierta a todos, incluso a los que se "durmieron" (HALT) en la lectura anterior.
  //    Se lee uno y se lo duerme.
  byte atqa[2];
  byte largo = sizeof(atqa);
  MFRC522::StatusCode estado = lector.PICC_WakeupA(atqa, &largo);
  if (estado != MFRC522::STATUS_OK && estado != MFRC522::STATUS_COLLISION) return 0;
  if (!lector.PICC_ReadCardSerial()) return 0;
  uids[leidos++] = uidActual();
  lector.PICC_HaltA();
  // 2) REQA solo despierta a los que NO estan dormidos: aparecen los demas, de a uno
  while (leidos < maximo && lector.PICC_IsNewCardPresent() && lector.PICC_ReadCardSerial()) {
    uids[leidos++] = uidActual();
    lector.PICC_HaltA();
  }
  return leidos;
}
