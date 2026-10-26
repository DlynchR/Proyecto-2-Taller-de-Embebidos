SUMMARY = "Imagen EdgeAI: mesa de ayuda local con Ollama para Raspberry Pi 4"
DESCRIPTION = "Imagen de consola (sin entorno gráfico) con Ollama, la mesa de ayuda EdgeAI, \
el kiosco en tty1, la interfaz web en el puerto 80 y acceso SSH para administración."
LICENSE = "MIT"

inherit core-image extrausers

IMAGE_FEATURES += "ssh-server-openssh allow-root-login"

IMAGE_INSTALL = "\
    packagegroup-core-boot \
    packagegroup-edgeai \
    ${CORE_IMAGE_EXTRA_INSTALL} \
"
# Modelos dentro de la imagen (opcional, ver local.conf).
IMAGE_INSTALL:append = " ${@'edgeai-models' if d.getVar('EDGEAI_PRELOAD_MODELS') == '1' else ''}"

IMAGE_LINGUAS = ""

# Espacio libre en la raíz para descargar modelos en la Pi (6 GiB, en KiB).
# La imagen .wic resultante ocupa ~7.5 GB: use una microSD de 16 GB o más.
IMAGE_ROOTFS_EXTRA_SPACE = "6291456"

IMAGE_FSTYPES = "wic.bz2 wic.bmap"

# Contraseña de root (por defecto "edgeai"). Cámbiela en edgeai-secrets.conf:
#   openssl passwd -6 'nueva-clave'   y escape cada $ como \$
EDGEAI_ROOT_PASSWORD_HASH ??= "\$6\$edgeai2026\$Bh6OE2BRjZ0dGI9PQVY/ax7o9dA7NPWYwpL.rN0HGDdzAlgvYeNI4nfNHD5vWnO04gGuPXdkHI9/JMQieYwKq1"
EXTRA_USERS_PARAMS = "usermod -p '${EDGEAI_ROOT_PASSWORD_HASH}' root;"

COMPATIBLE_MACHINE = "^raspberrypi4-64$"