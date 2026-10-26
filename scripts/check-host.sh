#!/usr/bin/env bash
# Verifica los requisitos de las compilaciones wrynose y QEMU.
set -euo pipefail
source "$(dirname "$0")/common.sh"

fail=0
ok()  { printf '  [OK]  %s\n' "$*"; }
bad() { printf '  [!!]  %s\n' "$*"; fail=1; }

info "Sistema operativo"
if [ -r /etc/os-release ]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    ok "$PRETTY_NAME (BitBake verifica la compatibilidad del host)"
fi
if [ "$(uname -m)" = "x86_64" ]; then ok "arquitectura x86_64"; else warn "arquitectura $(uname -m): Yocto se prueba sobre x86_64"; fi

info "Recursos"
free_gb=$(df -Pk "$REPO_ROOT" | awk 'NR==2 {print int($4/1024/1024)}')
if [ "$free_gb" -ge 100 ]; then ok "disco libre: ${free_gb} GB"
elif [ "$free_gb" -ge 70 ]; then warn "disco libre: ${free_gb} GB (justo; se recomiendan 100 GB)"
else bad "disco libre: ${free_gb} GB (mínimo ~70 GB con rm_work, recomendado 100 GB)"; fi
mem_gb=$(awk '/MemTotal/ {print int($2/1024/1024)}' /proc/meminfo)
cpus=$(nproc)
if [ "$mem_gb" -ge 8 ]; then ok "RAM: ${mem_gb} GB, CPUs: ${cpus}"; else warn "RAM: ${mem_gb} GB, CPUs: ${cpus} (con poca RAM baje BB_NUMBER_THREADS)"; fi

info "Herramientas del host"
for cmd in gawk wget git diffstat unzip makeinfo gcc g++ chrpath socat cpio python3 xz zstd file perl patch tar bzip2 curl jq unshare; do
    if command -v "$cmd" > /dev/null 2>&1; then ok "$cmd"; else bad "falta $cmd"; fi
done
if python3 -c 'import jinja2, git, pexpect, subunit' 2> /dev/null; then
    ok "módulos de Python (jinja2, git, pexpect, subunit)"
else
    bad "faltan módulos de Python (python3-jinja2 python3-git python3-pexpect python3-subunit)"
fi
if command -v bmaptool > /dev/null 2>&1; then ok "bmaptool (para grabar la microSD)"; else warn "falta bmaptool (opcional: sudo apt install bmap-tools)"; fi

info "Locale"
if locale -a 2> /dev/null | grep -qi '^en_US.utf8$'; then ok "en_US.UTF-8"; else bad "falta el locale en_US.UTF-8 (sudo locale-gen en_US.UTF-8)"; fi

info "Espacios de nombres de usuario y red"
if unshare -Urn true 2> /dev/null; then
    ok "prueba de user/network namespaces correcta; confirme tambien ejecutando BitBake"
else
    bad "No se pueden crear user/network namespaces. Revise los permisos y el perfil AppArmor de BitBake."
fi

if [ "$fail" -ne 0 ]; then
    cat <<'TXT'

Instale lo que falta (Ubuntu/Debian):
  sudo apt install gawk wget git diffstat unzip texinfo gcc build-essential chrpath socat \
       cpio python3 python3-pip python3-pexpect xz-utils debianutils iputils-ping python3-git \
    python3-jinja2 python3-subunit zstd liblz4-tool file locales libacl1 bmap-tools curl jq
  sudo locale-gen en_US.UTF-8
TXT
    exit 1
fi
info "El host cumple los requisitos."
