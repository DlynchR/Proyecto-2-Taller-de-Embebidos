SUMMARY = "Paquetes de la imagen EdgeAI"
DESCRIPTION = "Agrupa la aplicación, Ollama y las utilidades de operación de la mesa de ayuda."

# Depende de paquetes propios de la placa (firmware, Ollama aarch64).
PACKAGE_ARCH = "${MACHINE_ARCH}"

inherit packagegroup

PACKAGES = "${PN} ${PN}-tools"

RDEPENDS:${PN} = "\
    edgeai-helpdesk \
    edgeai-network \
    ollama-bin \
    ${PN}-tools \
"

# Utilidades para administrar y depurar la Pi en el sitio (todas en poky).
RDEPENDS:${PN}-tools = "\
    ca-certificates \
    curl \
    iw \
    less \
    procps \
    sqlite3 \
    tzdata \
    util-linux \
    vim-tiny \
"

RDEPENDS:${PN}-tools:append:raspberrypi4-64 = " linux-firmware-rpidistro-bcm43455"

# Wi-Fi integrado de la RPi4 (CYW43455). El firmware solo no basta: sin estos
# módulos no aparece wlan0. Antes se copiaban a mano a la microSD y se corría
# depmod/modprobe; ahora entran en la imagen y udev los carga al arrancar.
RDEPENDS:${PN}:append:raspberrypi4-64 = "\
    kernel-module-brcmfmac \
    kernel-module-brcmfmac-cyw \
    kernel-module-brcmutil \
    kernel-module-cfg80211 \
    kernel-module-rfkill \
"
RDEPENDS:${PN}:append:qemuarm64 = " edgeai-qemu-tests"
