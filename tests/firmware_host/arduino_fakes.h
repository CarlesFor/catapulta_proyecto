#pragma once
#include <string>
#include <map>
#include <vector>
#include <functional>
#include <sstream>
#include <iomanip>
#include <cstdint>

class String {
 public:
  std::string value;
  String() = default;
  String(const char* text): value(text) {}
  String(std::string text): value(text) {}
  String(int number): value(std::to_string(number)) {}
  String(unsigned long number): value(std::to_string(number)) {}
  String(float number, int places) {
    std::ostringstream stream;
    stream << std::fixed << std::setprecision(places) << number;
    value = stream.str();
  }
  size_t length() const { return value.length(); }
  const char* c_str() const { return value.c_str(); }
  char operator[](size_t index) const { return value[index]; }
  String& operator+=(const String& other) { value += other.value; return *this; }
  friend String operator+(const String& left, const String& right) {
    return left.value + right.value;
  }
  friend bool operator==(const String& left, const String& right) {
    return left.value == right.value;
  }
};

unsigned long fakeNow = 0;
unsigned long millis() { return fakeNow; }
struct SerialFake {
  void begin(int) {}
  template<class T> void print(const T&) {}
  template<class T> void println(const T&) {}
} Serial;

class Servo {
 public:
  std::vector<int> positions;
  void attach(int) {}
  void write(int angle) { positions.push_back(angle); }
};

const int WIFI_STA = 1;
const int WL_CONNECTED = 3;
struct WifiFake {
  void mode(int) {}
  void setAutoReconnect(bool) {}
  void begin(const char*, const char*) {}
  int status() { return WL_CONNECTED; }
  void reconnect() {}
  String localIP() { return "192.0.2.1"; }
} WiFi;

const int HTTP_GET = 1;
const int HTTP_POST = 2;
class WebServer {
 public:
  std::map<std::pair<std::string,int>,std::function<void()>> routes;
  std::map<std::string,String> arguments;
  int code = 0;
  String response;
  explicit WebServer(int) {}
  bool hasArg(const char* key) { return arguments.count(key) != 0; }
  String arg(const char* key) { return arguments[key]; }
  void send(int status, const char*, const String& body) { code = status; response = body; }
  void sendHeader(const char*, const char*) {}
  void on(const char* path, int method, std::function<void()> callback) {
    routes[{path, method}] = callback;
  }
  void onNotFound(std::function<void()>) {}
  void begin() {}
  void handleClient() {}
};
