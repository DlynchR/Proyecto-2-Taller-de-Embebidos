# Agrega a /boot/config.txt los overlays de los LEDs del semáforo de la mesa de ayuda.
# Cada línea gpio-led crea /sys/class/leds/<label>. Solo aplica con DISTRO = "edgeai".
# Los pines (numeración BCM) se definen en conf/distro/edgeai.conf (ver docs/hardware.md).

RPI_EXTRA_CONFIG:append:edgeai = "\n# --- EdgeAI: semaforo de LEDs ---\ndtoverlay=gpio-led,gpio=${EDGEAI_GPIO_VERDE},label=edgeai-verde\ndtoverlay=gpio-led,gpio=${EDGEAI_GPIO_AMARILLO},label=edgeai-amarillo\ndtoverlay=gpio-led,gpio=${EDGEAI_GPIO_ROJO},label=edgeai-rojo\n"
