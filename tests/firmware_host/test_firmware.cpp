#include <cassert>
#include <iostream>
#include <limits>
#include "../../catapult_code/sketch_aug19a/sketch_aug19a.ino"

void request(const char* id, const char* power) {
  servidor.arguments = {{"id", id}, {"potencia", power}};
  disparar();
}

int main() {
  setup();
  assert(myservo.positions.back() == 120);
  auto writes = myservo.positions.size();
  servidor.routes.at({"/disparar", HTTP_GET})();
  assert(servidor.code == 405 && myservo.positions.size() == writes);

  for (const char* power : {"", "0.09", "1.01", "nan", "inf", "abc", "0.5x", "1e30"}) {
    request("invalid", power);
    assert(servidor.code == 400 && myservo.positions.size() == writes);
  }
  request("invalid-id\"", "0.5");
  assert(servidor.code == 400);
  servidor.arguments.clear();
  disparar();
  assert(servidor.code == 400);

  request("full", "1.0");
  assert(servidor.code == 202 && myservo.positions.back() == 0 && disparoEnCurso);
  writes = myservo.positions.size();
  request("full", "1.0");
  assert(servidor.code == 202 && myservo.positions.size() == writes);
  request("full", "0.98");
  assert(servidor.code == 409 && myservo.positions.size() == writes);
  request("busy", "0.98");
  assert(servidor.code == 409 && myservo.positions.size() == writes);
  responderEstado();
  assert(servidor.response.value.find("\"estado\":\"disparando\"") != std::string::npos);
  fakeNow = 999;
  actualizarServo();
  assert(disparoEnCurso && myservo.positions.size() == writes);
  fakeNow = 1000;
  actualizarServo();
  assert(!disparoEnCurso && myservo.positions.back() == 120);
  writes = myservo.positions.size();
  request("full", "1.0");
  assert(servidor.code == 202 && myservo.positions.size() == writes);
  responderEstado();
  assert(servidor.response.value.find("\"estado\":\"listo\"") != std::string::npos);
  assert(servidor.response.value.find("\"last_shot_id\":\"full\"") != std::string::npos);

  request("edge", "0.10");
  assert(servidor.code == 202 && myservo.positions.back() == 108);
  fakeNow = 2000;
  actualizarServo();
  request("near", "0.98");
  assert(servidor.code == 202 && myservo.positions.back() == 2);
  fakeNow = 3000;
  actualizarServo();

  fakeNow = std::numeric_limits<unsigned long>::max() - 499;
  request("wrap", "0.5");
  assert(servidor.code == 202 && myservo.positions.back() == 60);
  fakeNow += 999;
  actualizarServo();
  assert(disparoEnCurso);
  fakeNow += 1;
  actualizarServo();
  assert(!disparoEnCurso && myservo.positions.back() == 120);
  std::cout << "PASS: firmware validation, routes, angles, busy, duplicates, timer and rollover\n";
}
