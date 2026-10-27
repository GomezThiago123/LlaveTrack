#include "lcd.h"

#include <LiquidCrystal_I2C.h>
#include <Wire.h>

#include "config.h"

namespace {
LiquidCrystal_I2C *lcd = nullptr;
String mostrado1, mostrado2;

bool responde(byte direccion) {
  Wire.beginTransmission(direccion);
  return Wire.endTransmission() == 0;
}

String recortar(const String &texto) {
  return texto.length() > 16 ? texto.substring(0, 16) : texto;
}
}  // namespace

void lcdIniciar() {
  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL);
  byte direccion = responde(0x27) ? 0x27 : responde(0x3F) ? 0x3F : 0;
  if (!direccion) {
    Serial.println("[lcd] No se encontro el LCD (0x27 ni 0x3F)");
    return;
  }
  Serial.printf("[lcd] LCD en 0x%02X\n", direccion);
  lcd = new LiquidCrystal_I2C(direccion, 16, 2);
  lcd->init();
  lcd->backlight();
}

void lcdMensaje(const String &linea1, const String &linea2) {
  String l1 = recortar(linea1), l2 = recortar(linea2);
  if (l1 == mostrado1 && l2 == mostrado2) return;
  mostrado1 = l1;
  mostrado2 = l2;
  Serial.printf("[lcd] [%-16s] [%-16s]\n", l1.c_str(), l2.c_str());
  if (!lcd) return;
  lcd->clear();
  lcd->setCursor(0, 0);
  lcd->print(l1);
  lcd->setCursor(0, 1);
  lcd->print(l2);
}
