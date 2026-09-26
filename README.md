# Minijuego de la catapulta

Detén el marcador lo más cerca posible del centro de la barra. El centro verde da el 100 % del recorrido del servo; los extremos rojos, el 10 %.

## Cómo arrancar

1. Abre `catapult_code/sketch_aug19a/sketch_aug19a.ino` en Arduino IDE. Copia `wifi_config.h.example` como `wifi_config.h` en la misma carpeta y escribe allí tu red y contraseña (este archivo queda excluido de Git). Selecciona la placa **ESP32 Dev Module** y su puerto.
2. Sube el sketch actualizado. El servo usa **GPIO 26**, empieza en **120°** y vuelve a esa posición un segundo después de cada disparo.
3. Comprueba la IP en el monitor serie a **115200 baudios**. El ordenador y el ESP32 deben estar en la misma red local.
4. Desde la carpeta del proyecto, ejecuta:

   ```powershell
   py python_code/app_catapulta.py
   ```

La aplicación utiliza Tkinter y la biblioteca estándar de Python; no necesita paquetes de `pip`. La IP inicial `192.0.2.1` es solo un ejemplo: sustitúyela en la interfaz por la que indique el monitor serie.

Para abrir directamente en modo práctica, sin conectar la placa:

```powershell
py python_code/app_catapulta.py --demo
```

## Cómo jugar

- **Práctica:** juega sin enviar órdenes de disparo al ESP32.
- **Modo real:** utiliza la IP de la placa para enviar el resultado de cada tiro.
- Pulsa **Espacio** mientras se mueve el marcador para detenerlo. En modo real, esto envía una única orden de disparo.
- Pulsa **Espacio** otra vez para iniciar una nueva ronda.

La aplicación no reintenta automáticamente los disparos si falla la conexión. Si detecta el firmware anterior, te pedirá que subas el sketch actualizado.

## Cómo se calcula el tiro

La posición `x` va de `0` (extremo izquierdo) a `1` (extremo derecho):

```text
precisión = 1 - abs(2 × x - 1)
factor = 0,10 + 0,90 × precisión
recorrido = 120° × factor
posición objetivo = 120° - recorrido
```

| Posición del marcador | Factor | Recorrido | Posición objetivo |
| --- | --- | --- | --- |
| Centro | 1,00 | 120° | 0° |
| A mitad de camino entre centro y extremo | 0,55 | 66° | 54° |
| Extremo | 0,10 | 12° | 108° |

El servo parte de 120°, se mueve hacia la posición objetivo y regresa a 120° tras un segundo. El porcentaje de potencia representa **recorrido angular**, no energía ni distancia de lanzamiento medidas.

El ESP32 redondea el recorrido a grados enteros antes de ordenar el movimiento. Por ejemplo, un factor de 0,98 produce 117,6° de recorrido calculado y una orden de 118° de recorrido.

## Archivos y comunicación

- `python_code/app_catapulta.py`: interfaz, animación y controles del juego.
- `python_code/game_core.py`: cálculo del tiro y comunicación HTTP.
- `catapult_code/sketch_aug19a/sketch_aug19a.ino`: conexión Wi-Fi, servidor y control del servo.

`GET /estado` devuelve JSON con la versión de API `1`. `POST /disparar` recibe la potencia y un identificador de la orden. El ESP32 controla el movimiento y el retorno del servo.

Para ejecutar las pruebas desde la carpeta del proyecto:

```powershell
py -m unittest discover -s python_code/tests -v
```

Estas pruebas comprueban el software; el movimiento y el resultado del lanzamiento necesitan validación con la catapulta física.

## Privacidad

Las credenciales Wi-Fi se guardan solo en `wifi_config.h`, excluido de Git. Publica únicamente la plantilla `wifi_config.h.example`. Los binarios compilados pueden contener credenciales y también quedan excluidos, junto con cachés y archivos del editor.

## Herramientas adicionales

- `python_code/prueba_conexion.py`: comprueba `/estado`; usa `--ip` con la IP de tu placa.
- `tests/firmware_host/`: pruebas del firmware con dobles de Arduino, sin placa.
- `tools/build_hardware_guide.py`: genera la guía PDF; requiere ReportLab y las fuentes Arial de Windows.

Para ejecutar las pruebas del firmware con un compilador C++17, crea `.build` si no existe y ejecuta:

```powershell
g++ -std=c++17 -I tests/firmware_host tests/firmware_host/test_firmware.cpp -o .build/test_firmware.exe
.build/test_firmware.exe
```

Las pruebas del firmware requieren `wifi_config.h`; para pruebas sin placa basta con copiar la plantilla sin cambiar sus valores.

Guía de montaje: [descargar PDF](docs/Guia_montaje_catapulta_ESP32.pdf).
