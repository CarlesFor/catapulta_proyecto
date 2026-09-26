#include <ESP32Servo.h>
#include <WiFi.h>
#include <WebServer.h>
#include <math.h>
#include <stdlib.h>

#include "wifi_config.h"

const char* ssid = CATAPULT_WIFI_SSID;
const char* password = CATAPULT_WIFI_PASSWORD;
WebServer servidor(80);
Servo myservo;

const int servoPin = 26;
const int anguloReposo = 120;
const int recorridoMaximo = 120;
const unsigned long duracionDisparoMs = 1000;
const unsigned long intervaloReconexionMs = 10000;
const int cantidadRegistros = 12;

bool disparoEnCurso = false;
bool wifiEstabaConectado = false;
unsigned long inicioDisparoMs = 0;
unsigned long ultimoIntentoWifiMs = 0;
String ultimoDisparoId;

// Una peticion repetida con el mismo identificador no vuelve a mover el servo.
// Conservamos los 12 ultimos identificadores hasta reiniciar la placa.
struct RegistroDisparo {
  String id;
  float potencia;
  int recorrido;
  int objetivo;
};

RegistroDisparo registros[cantidadRegistros];
int siguienteRegistro = 0;

void enviarError(int codigo, const char* mensaje) {
  servidor.send(codigo, "application/json", String("{\"error\":\"") + mensaje + "\"}");
}

bool identificadorValido(const String& id) {
  if (id.length() == 0 || id.length() > 64) {
    return false;
  }
  for (unsigned int i = 0; i < id.length(); i++) {
    char letra = id[i];
    bool valido = (letra >= 'a' && letra <= 'z') ||
                  (letra >= 'A' && letra <= 'Z') ||
                  (letra >= '0' && letra <= '9') ||
                  letra == '-' || letra == '_';
    if (!valido) {
      return false;
    }
  }
  return true;
}

void responderDisparo(const RegistroDisparo& registro, bool repetido) {
  String respuesta = "{\"aceptado\":true,\"id\":\"" + registro.id + "\"";
  respuesta += ",\"potencia\":" + String(registro.potencia, 6);
  respuesta += ",\"recorrido_grados\":" + String(registro.recorrido);
  respuesta += ",\"angulo_objetivo\":" + String(registro.objetivo);
  respuesta += ",\"duracion_ms\":" + String(duracionDisparoMs);
  respuesta += ",\"repetido\":";
  respuesta += repetido ? "true}" : "false}";
  servidor.send(202, "application/json", respuesta);
}

void responderEstado() {
  String respuesta = "{\"api_version\":1,\"estado\":\"";
  respuesta += disparoEnCurso ? "disparando" : "listo";
  respuesta += "\",\"reposo\":" + String(anguloReposo);
  respuesta += ",\"recorrido_maximo\":" + String(recorridoMaximo);
  respuesta += ",\"duracion_ms\":" + String(duracionDisparoMs);
  respuesta += ",\"last_shot_id\":\"" + ultimoDisparoId + "\"}";
  servidor.sendHeader("Cache-Control", "no-store");
  servidor.send(200, "application/json", respuesta);
}

void disparar() {
  if (!servidor.hasArg("potencia") || !servidor.hasArg("id")) {
    enviarError(400, "Faltan potencia e id");
    return;
  }

  String id = servidor.arg("id");
  String textoPotencia = servidor.arg("potencia");
  char* fin;
  float potencia = strtof(textoPotencia.c_str(), &fin);
  if (!identificadorValido(id) || fin == textoPotencia.c_str() || *fin != '\0' ||
      !isfinite(potencia) || potencia < 0.10f || potencia > 1.00f) {
    enviarError(400, "Usa un id valido y potencia entre 0.10 y 1.00");
    return;
  }

  for (int i = 0; i < cantidadRegistros; i++) {
    if (registros[i].id == id) {
      if (fabsf(registros[i].potencia - potencia) > 0.000001f) {
        enviarError(409, "Este id ya pertenece a otra potencia");
      } else {
        responderDisparo(registros[i], true);
      }
      return;
    }
  }

  if (disparoEnCurso) {
    enviarError(409, "La catapulta esta terminando el disparo anterior");
    return;
  }

  RegistroDisparo& registro = registros[siguienteRegistro];
  registro.id = id;
  registro.potencia = potencia;
  // La potencia representa el recorrido angular, no una medida de fuerza real.
  registro.recorrido = (int)roundf(recorridoMaximo * potencia);
  registro.objetivo = anguloReposo - registro.recorrido;
  siguienteRegistro = (siguienteRegistro + 1) % cantidadRegistros;

  ultimoDisparoId = id;
  myservo.write(registro.objetivo);
  inicioDisparoMs = millis();
  disparoEnCurso = true;
  responderDisparo(registro, false);
}

void actualizarServo() {
  // millis() permite atender la red mientras transcurre el segundo de espera.
  if (disparoEnCurso && millis() - inicioDisparoMs >= duracionDisparoMs) {
    myservo.write(anguloReposo);
    disparoEnCurso = false;
  }
}

void actualizarWifi() {
  bool conectado = WiFi.status() == WL_CONNECTED;
  if (conectado && !wifiEstabaConectado) {
    Serial.print("WiFi conectado. Mi direccion IP es: ");
    Serial.println(WiFi.localIP());
  }
  if (!conectado && millis() - ultimoIntentoWifiMs >= intervaloReconexionMs) {
    ultimoIntentoWifiMs = millis();
    Serial.println("Intentando conectar al WiFi...");
    WiFi.reconnect();
  }
  wifiEstabaConectado = conectado;
}

void setup() {
  Serial.begin(115200);

  // El montaje original dispara hacia 0 grados y regresa a 120 grados.
  myservo.attach(servoPin);
  myservo.write(anguloReposo);

  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(ssid, password);
  ultimoIntentoWifiMs = millis();
  Serial.println("Conectando al WiFi...");

  servidor.on("/estado", HTTP_GET, responderEstado);
  servidor.on("/disparar", HTTP_POST, disparar);
  servidor.on("/disparar", HTTP_GET, []() {
    servidor.sendHeader("Allow", "POST");
    enviarError(405, "Para disparar utiliza POST desde la aplicacion");
  });
  servidor.onNotFound([]() {
    enviarError(404, "Ruta no encontrada");
  });
  servidor.begin();
  Serial.println("Servidor HTTP iniciado");
}

void loop() {
  actualizarServo();
  servidor.handleClient();
  actualizarWifi();
}
