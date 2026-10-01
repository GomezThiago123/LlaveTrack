# Simulador del equipo LlaveTrack. En la Fase 1 se conecta a Mosquitto y publica
# los mismos eventos que el ESP32 (ver docs/protocolo-mqtt.md).

AYUDA = """
Simulador LlaveTrack (todavia sin implementar: llega en la Fase 1)

Uso (desde backend/, con el .venv activado): python simulador/simulador.py <comando>

Comandos previstos:
  retirar <codigo>    Ingresa un codigo de 6 digitos y confirma el retiro
  timeout <codigo>    Ingresa el codigo pero no retira la llave (retiro_timeout)
  devolver <uid>      Cuelga la llave con ese UID en el slot de la ventana
"""

if __name__ == "__main__":
    print(AYUDA)
