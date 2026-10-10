# Catapulta con ESP32

Un minijuego en el ordenador mueve un servo por Wi-Fi: pulsa **Espacio** cerca del centro de la barra para conseguir más recorrido.

**¿Es tu primera vez? Sigue la [guía desde cero](docs/GUIA_DESDE_CERO.md), en orden.** También puedes [descargar el mismo contenido en PDF](docs/Guia_montaje_catapulta_ESP32.pdf). La guía está orientada a Windows y no requiere saber usar Git ni programar.

## Qué podrás hacer

1. Descargar el proyecto e instalar los programas.
2. Probar el juego sin conectar ninguna placa.
3. Cablear el ESP32 y el servo con un esquema.
4. Configurar tu Wi-Fi y cargar el programa en el ESP32.
5. Conectar el juego y comprobar el movimiento antes de montar el brazo.

**La estructura física todavía no tiene un plano reproducible:** faltan el modelo exacto de servo y fuente, las medidas y las fijaciones. La guía explica el montaje general y señala esos datos pendientes. El software se ha probado automáticamente; el conjunto mecánico necesita validación con el montaje real.

## Primero, prueba el juego sin hardware

Descarga **Code → Download ZIP** y pulsa **Extraer todo**. Instala [Python para Windows](https://www.python.org/downloads/windows/). Abre la carpeta extraída que contiene este README, escribe `powershell` en la barra de direcciones del Explorador y pulsa Intro.

Ejecuta:

```powershell
py python_code/app_catapulta.py --demo
```

Debe abrirse una ventana con **PRÁCTICA** y una barra en movimiento. Haz clic en la barra y pulsa **Espacio** para detenerla; vuelve a pulsarlo para otra ronda. No se necesita placa en este modo. Si no se abre, consulta el apartado de problemas de la guía.

## Cuando ya hayas preparado la placa

Abre el juego con el comando anterior. Desmarca **Práctica**, sustituye la IP de ejemplo por la que muestre el monitor serie del ESP32 y pulsa **Conectar**. Espera a ver **ESP32 CONECTADO** antes de probar el servo.

La IP `192.0.2.1` es solo un ejemplo; no corresponde a tu placa. La guía explica cómo obtener la tuya.

## Dónde está cada cosa

| Archivo | Para qué sirve |
| --- | --- |
| [Guía desde cero](docs/GUIA_DESDE_CERO.md) | Materiales, instalación, cableado, carga, primer tiro y problemas |
| [Guía PDF](docs/Guia_montaje_catapulta_ESP32.pdf) | La misma guía para guardar o imprimir |
| [Programa del ESP32](catapult_code/sketch_aug19a/sketch_aug19a.ino) | Se abre con Arduino IDE y se carga en la placa |
| [Plantilla Wi-Fi](catapult_code/sketch_aug19a/wifi_config.h.example) | Se copia como `wifi_config.h` y se rellena solo en tu ordenador |
| [Juego](python_code/app_catapulta.py) | Se ejecuta en el ordenador |
| [Referencia técnica](docs/REFERENCIA_TECNICA.md) | Fórmulas, comunicación y pruebas para quien quiera modificar el proyecto |

## Tus datos permanecen locales

Escribe tu red y contraseña únicamente en `wifi_config.h`, que Git ignora. También se excluyen los binarios compilados, porque pueden contener esas credenciales. No compartas ese archivo ni un ZIP de tu carpeta de trabajo sin revisarlo: `.gitignore` solo protege las operaciones de Git.

La aplicación usa Tkinter y la biblioteca estándar de Python; para jugar no necesitas instalar paquetes con `pip`.
