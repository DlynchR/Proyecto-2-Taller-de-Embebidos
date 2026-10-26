# Hardware y conexiones

## Lista de materiales

| Cant. | Componente | Notas |
|---|---|---|
| 1 | Raspberry Pi 4 Model B, 4 GB o 8 GB | 8 GB permite usar un LLM de 3B |
| 1 | microSD 16 GB o más, A1/A2 | la imagen ocupa ~7.5 GB |
| 1 | Fuente USB-C 5 V / 3 A | una fuente débil causa reinicios bajo carga |
| 1 | Disipador o ventilador | la inferencia mantiene la CPU al 100 % por varios segundos |
| 1 | Monitor HDMI + cable micro-HDMI | conectar en **HDMI0** (junto a la alimentación) |
| 1 | Teclado USB | kiosco en tty1 |
| 3 | LED 5 mm (verde, amarillo, rojo) | semáforo de estado |
| 3 | Resistencia 330 Ω | limitan la corriente a ~5 mA (los GPIO dan 3.3 V) |
| — | Protoboard y cables dupont hembra-macho | |

Los LEDs son opcionales: sin ellos la aplicación funciona y el panel web muestra los LEDs
simulados.

## Conexiones (numeración BCM)

| Señal | GPIO (BCM) | Pin físico | Conexión |
|---|---|---|---|
| LED verde | GPIO17 | 11 | GPIO → 330 Ω → ánodo LED; cátodo → GND |
| LED amarillo | GPIO27 | 13 | igual |
| LED rojo | GPIO22 | 15 | igual |
| GND | — | 9, 14 | tierra común |

```
            3V3 (1) (2)  5V
          GPIO2 (3) (4)  5V
          GPIO3 (5) (6)  GND
          GPIO4 (7) (8)  GPIO14
            GND (9) (10) GPIO15
  verde → GPIO17 (11) (12) GPIO18
amarillo→ GPIO27 (13) (14) GND
   rojo → GPIO22 (15) (16) GPIO23
```

Los pines elegidos no interfieren con UART (14/15), I2C (2/3) ni SPI (7–11). Para cambiarlos,
defina `EDGEAI_GPIO_VERDE`, `EDGEAI_GPIO_AMARILLO` y `EDGEAI_GPIO_ROJO` en
`build/raspberrypi4-64/conf/local.conf` y reconstruya.

## Cómo llegan los LEDs a la aplicación

1. `rpi-config_%.bbappend` escribe en `/boot/config.txt` una línea `dtoverlay=gpio-led` por
   cada LED.
2. Al arrancar, el firmware aplica los overlays y el kernel crea
   `/sys/class/leds/edgeai-{verde,amarillo,rojo}`.
3. La regla udev `90-edgeai.rules` da al grupo `edgeai` permiso de escritura sobre
   `brightness`, así la aplicación no necesita ejecutarse como root.
4. `indicators.py` escribe `0` o `1` en `brightness`.

## Significado de los LEDs

| LED | Encendido | Parpadeo |
|---|---|---|
| Verde | sistema listo | lento: cargando o descargando modelos |
| Amarillo | hay tiquetes en cola | el LLM está redactando una respuesta |
| Rojo | hay tiquetes urgentes pendientes | rápido: Ollama no responde |

## Verificación en la Pi

```bash
grep edgeai /boot/config.txt          # overlays configurados
ls /sys/class/leds/                    # deben aparecer edgeai-verde, -amarillo, -rojo
systemctl stop edgeai-helpdesk && edgeai-admin leds probar && systemctl start edgeai-helpdesk
```
