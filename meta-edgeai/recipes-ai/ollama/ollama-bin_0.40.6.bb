SUMMARY = "Ollama: LLMs y modelos de decisión System One (binario aarch64)"
DESCRIPTION = "Instala el binario precompilado de Ollama para Linux arm64 con solo los \
backends de CPU. Desde la versión 0.35 Ollama expone el endpoint /v1/systemone \
(API JEV de TypeSafe) para modelos de decisión como tev1 y nimble, además de la \
API habitual de LLMs (/api/chat)."
HOMEPAGE = "https://ollama.com"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

# Se usa el binario oficial en lugar de compilar desde fuente: compilar Ollama
# exige Go + CMake/ggml con módulos descargados en tiempo de build, lo que en
# Yocto complica la reproducibilidad. Ver docs/recetas.md (decisiones de diseño).
SRC_URI = "https://github.com/ollama/ollama/releases/download/v${PV}/ollama-linux-arm64.tar.zst;downloadfilename=ollama-linux-arm64-${PV}.tar.zst;subdir=ollama-${PV} \
           file://ollama.service \
           file://ollama.env \
           "
# Si cambia PV, actualice el hash con: ./scripts/update-ollama.sh <versión>
SRC_URI[sha256sum] = "0a279d9428ad17b06fdb7dddf3b059b2c148433585fa3b30676a102fc459bb9f"

S = "${UNPACKDIR}/ollama-${PV}"

# El binario oficial solo existe para aarch64: la placa debe ser raspberrypi4-64.
COMPATIBLE_HOST = "aarch64.*-linux"

inherit systemd useradd

USERADD_PACKAGES = "${PN}"
USERADD_PARAM:${PN} = "--system --home-dir ${localstatedir}/lib/ollama --no-create-home \
                       --shell /bin/false --user-group ollama"

SYSTEMD_SERVICE:${PN} = "ollama.service"
SYSTEMD_AUTO_ENABLE = "enable"

# Backends que no aplican a la RPi4 (GPU NVIDIA/AMD, Jetson, Vulkan, MLX): se descartan.
OLLAMA_EXCLUDE_BACKENDS ?= "cuda* *jetpack* rocm* vulkan* mlx*"

do_configure[noexec] = "1"
do_compile[noexec] = "1"

do_install() {
    if [ ! -x ${S}/bin/ollama ]; then
        bbfatal "No se encontró bin/ollama en el archivo descargado (¿cambió el formato del release?)"
    fi
    install -d ${D}${bindir}
    install -m 0755 ${S}/bin/ollama ${D}${bindir}/ollama

    # Ollama busca sus bibliotecas en <bin>/../lib/ollama, por eso van en
    # /usr/lib/ollama (nonarch_libdir) aunque libdir sea /usr/lib64 en aarch64.
    if [ -d ${S}/lib/ollama ]; then
        install -d ${D}${nonarch_libdir}
        set -f
        excludes=""
        for pat in ${OLLAMA_EXCLUDE_BACKENDS}; do
            excludes="$excludes --exclude=ollama/$pat"
        done
        tar -C ${S}/lib $excludes -cf - ollama | tar -C ${D}${nonarch_libdir} --no-same-owner -xf -
        set +f
    else
        bbwarn "El archivo no trae lib/ollama: se instala solo el binario"
    fi

    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${UNPACKDIR}/ollama.service ${D}${systemd_system_unitdir}/ollama.service
    install -d ${D}${sysconfdir}/default
    install -m 0644 ${UNPACKDIR}/ollama.env ${D}${sysconfdir}/default/ollama

    install -d -m 0750 ${D}${localstatedir}/lib/ollama
    install -d -m 0750 ${D}${localstatedir}/lib/ollama/models
    chown -R ollama:ollama ${D}${localstatedir}/lib/ollama
}

FILES:${PN} += "\
    ${nonarch_libdir}/ollama \
    ${localstatedir}/lib/ollama \
    ${systemd_system_unitdir}/ollama.service \
"
CONFFILES:${PN} = "${sysconfdir}/default/ollama"

# Binarios precompilados: no se re-strippean ni se separan símbolos, y sus
# bibliotecas internas (libggml-*) no se publican como proveedoras del sistema.
INHIBIT_PACKAGE_STRIP = "1"
INHIBIT_PACKAGE_DEBUG_SPLIT = "1"
INHIBIT_SYSROOT_STRIP = "1"
EXCLUDE_FROM_SHLIBS = "1"
INSANE_SKIP:${PN} += "already-stripped ldflags dev-so file-rdeps libdir textrel buildpaths"

RDEPENDS:${PN} += "ca-certificates libgcc libstdc++"
RRECOMMENDS:${PN} += "libgomp"
