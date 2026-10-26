SUMMARY = "Mesa de ayuda EdgeAI: API, web, kiosco y administración"
DESCRIPTION = "Clasifica consultas con un modelo de decisión System One (endpoint /v1/systemone \
de Ollama) y redacta respuestas con un LLM local. Incluye servicios systemd, reglas udev \
para los LEDs del semáforo y la configuración del dominio."
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

# El código fuente vive en <repo>/app (EDGEAI_REPO_DIR se define en conf/layer.conf).
# Cualquier cambio en app/ cambia el checksum y la receta se reconstruye sola.
FILESEXTRAPATHS:prepend := "${EDGEAI_REPO_DIR}:"
SRC_URI = "file://app"
S = "${UNPACKDIR}/app"

inherit allarch systemd useradd

USERADD_PACKAGES = "${PN}"
USERADD_PARAM:${PN} = "--system --home-dir ${localstatedir}/lib/edgeai --no-create-home \
                       --shell /bin/false --user-group edgeai"

SYSTEMD_SERVICE:${PN} = "edgeai-helpdesk.service edgeai-kiosk.service edgeai-provision.service"
SYSTEMD_AUTO_ENABLE = "enable"

do_configure[noexec] = "1"
do_compile[noexec] = "1"

do_install() {
    # Paquete Python (solo biblioteca estándar) en /usr/lib/edgeai
    install -d ${D}${nonarch_libdir}/edgeai/edgeai_helpdesk/web
    install -m 0644 ${S}/edgeai_helpdesk/*.py ${D}${nonarch_libdir}/edgeai/edgeai_helpdesk/
    for f in ${S}/edgeai_helpdesk/web/*.html ${S}/edgeai_helpdesk/web/*.css ${S}/edgeai_helpdesk/web/*.js; do
        install -m 0644 "$f" ${D}${nonarch_libdir}/edgeai/edgeai_helpdesk/web/
    done

    # Comandos
    install -d ${D}${bindir}
    for b in edgeai-helpdesk edgeai-kiosk edgeai-admin edgeai-bench; do
        install -m 0755 ${S}/bin/$b ${D}${bindir}/$b
    done

    # Configuración y datos de demostración
    install -d ${D}${sysconfdir}/edgeai
    install -m 0644 ${S}/config/helpdesk.conf ${D}${sysconfdir}/edgeai/helpdesk.conf
    install -m 0644 ${S}/config/categorias.json ${D}${sysconfdir}/edgeai/categorias.json
    install -d ${D}${datadir}/edgeai
    install -m 0644 ${S}/config/casos_demo.json ${D}${datadir}/edgeai/casos_demo.json

    # Servicios systemd
    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${S}/systemd/*.service ${D}${systemd_system_unitdir}/
    install -d ${D}${systemd_unitdir}/system-preset
    install -m 0644 ${S}/systemd/00-edgeai-kiosk.preset ${D}${systemd_unitdir}/system-preset/
    # tty1 es del kiosco: se enmascara su getty (el inicio de sesión queda en tty2).
    install -d ${D}${sysconfdir}/systemd/system
    ln -sf /dev/null ${D}${sysconfdir}/systemd/system/getty@tty1.service

    # Integración con el sistema: LEDs (udev) y mensajes del kernel (sysctl)
    install -d ${D}${sysconfdir}/udev/rules.d ${D}${sysconfdir}/sysctl.d
    install -m 0644 ${S}/system/90-edgeai.rules ${D}${sysconfdir}/udev/rules.d/90-edgeai.rules
    install -m 0644 ${S}/system/90-edgeai-sysctl.conf ${D}${sysconfdir}/sysctl.d/90-edgeai.conf

    # Base de datos de tiquetes
    install -d -m 0750 ${D}${localstatedir}/lib/edgeai
    chown edgeai:edgeai ${D}${localstatedir}/lib/edgeai
}

FILES:${PN} += "\
    ${nonarch_libdir}/edgeai \
    ${datadir}/edgeai \
    ${systemd_system_unitdir} \
    ${systemd_unitdir}/system-preset/00-edgeai-kiosk.preset \
    ${localstatedir}/lib/edgeai \
"
CONFFILES:${PN} = "\
    ${sysconfdir}/edgeai/helpdesk.conf \
    ${sysconfdir}/edgeai/categorias.json \
"

# python3-modules: biblioteca estándar completa (http.server, sqlite3, urllib, json...).
# iproute2: el kiosco muestra las IP del equipo. kbd: loadkeys la-latin1 para el kiosco.
RDEPENDS:${PN} = "\
    iproute2 \
    kbd \
    kbd-keymaps \
    python3-core \
    python3-modules \
    python3-sqlite3 \
"
