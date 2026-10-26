SUMMARY = "Modelos de Ollama precargados en la imagen (opcional)"
DESCRIPTION = "Extrae en /var/lib/ollama/models un archivo generado con \
tools/export_models.py (modelo de decisión + LLM), para que la Raspberry Pi \
funcione sin internet desde el primer arranque. Se incluye en la imagen solo si \
EDGEAI_PRELOAD_MODELS = \"1\"."
# Cada modelo conserva su propia licencia (ver la ficha del modelo en ollama.com).
LICENSE = "CLOSED"

EDGEAI_MODELS_TARBALL ??= "${EDGEAI_REPO_DIR}/models/ollama-models.tar"

inherit allarch useradd

# Sin SRC_URI: el archivo se toma de EDGEAI_MODELS_TARBALL (pesa ~2 GB y no se versiona).

# Mismo usuario que crea ollama-bin (si ya existe, no se vuelve a crear).
USERADD_PACKAGES = "${PN}"
USERADD_PARAM:${PN} = "--system --home-dir ${localstatedir}/lib/ollama --no-create-home \
                       --shell /bin/false --user-group ollama"

do_configure[noexec] = "1"
do_compile[noexec] = "1"

# Reconstruir si el archivo de modelos cambia.
do_install[file-checksums] += "${@'${EDGEAI_MODELS_TARBALL}:True' if os.path.exists(d.getVar('EDGEAI_MODELS_TARBALL') or '') else ''}"

do_install() {
    if [ ! -f "${EDGEAI_MODELS_TARBALL}" ]; then
        bbfatal "No existe ${EDGEAI_MODELS_TARBALL}. Genérelo con tools/export_models.py o use EDGEAI_PRELOAD_MODELS = \"0\"."
    fi
    install -d -m 0750 ${D}${localstatedir}/lib/ollama/models
    tar -C ${D}${localstatedir}/lib/ollama/models --no-same-owner -xf "${EDGEAI_MODELS_TARBALL}"
    chown -R ollama:ollama ${D}${localstatedir}/lib/ollama
}

# /var/lib/ollama ya está en FILES:${PN} por defecto (${localstatedir}).
RDEPENDS:${PN} = "ollama-bin"
