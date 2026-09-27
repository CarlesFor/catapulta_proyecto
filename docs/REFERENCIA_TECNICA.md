# Referencia técnica

Los comandos se ejecutan desde la carpeta del proyecto.

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


## Regenerar la documentación

El juego no necesita estos paquetes. Solo para regenerar el PDF y el esquema:

```powershell
py -m pip install reportlab
py tools/build_hardware_guide.py
```

Edita docs/GUIA_DESDE_CERO.md: ese texto genera el PDF. El generador usa fuentes integradas.

## Pruebas del firmware sin placa

Copia la plantilla Wi-Fi como wifi_config.h; los valores de ejemplo bastan. Con un compilador C++17 instalado:

```powershell
New-Item -ItemType Directory -Force .build
g++ -std=c++17 -I tests/firmware_host tests/firmware_host/test_firmware.cpp -o .build/test_firmware.exe
.build/test_firmware.exe
```

Las pruebas no confirman el movimiento físico del servo.
