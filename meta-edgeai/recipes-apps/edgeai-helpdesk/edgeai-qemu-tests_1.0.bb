SUMMARY = "Simulador de Ollama para pruebas de integracion en QEMU"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

FILESEXTRAPATHS:prepend := "${EDGEAI_REPO_DIR}:"
SRC_URI = "file://tools/mock_ollama.py"
S = "${UNPACKDIR}"
COMPATIBLE_MACHINE = "^qemuarm64$"
PACKAGE_ARCH = "${MACHINE_ARCH}"

do_configure[noexec] = "1"
do_compile[noexec] = "1"

do_install() {
    install -d ${D}${libexecdir}/edgeai
    install -m 0644 ${UNPACKDIR}/tools/mock_ollama.py ${D}${libexecdir}/edgeai/mock_ollama.py
    install -d ${D}${sysconfdir}/systemd/system/ollama.service.d
    printf '%s\n' '[Service]' 'ExecStart=' \
        'ExecStart=/usr/bin/python3 ${libexecdir}/edgeai/mock_ollama.py --port 11434 --latencia-decision 0 --latencia-llm 0' \
        > ${D}${sysconfdir}/systemd/system/ollama.service.d/qemu.conf
    install -d ${D}${sysconfdir}/systemd/system/edgeai-provision.service.d
    printf '%s\n' '[Service]' 'ExecStartPost=' \
        > ${D}${sysconfdir}/systemd/system/edgeai-provision.service.d/qemu.conf
    printf '%s\n' 'Ollama simulado: esta imagen no valida inferencia real ni hardware Raspberry Pi.' \
        > ${D}${sysconfdir}/edgeai-qemu-testing
}

FILES:${PN} += "${libexecdir}/edgeai"
RDEPENDS:${PN} = "edgeai-helpdesk ollama-bin python3-modules"