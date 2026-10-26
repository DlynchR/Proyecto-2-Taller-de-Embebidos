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
    linux-firmware-rpidistro-bcm43455 \
    procps \
    sqlite3 \
    tzdata \
    util-linux \
    vim-tiny \
"