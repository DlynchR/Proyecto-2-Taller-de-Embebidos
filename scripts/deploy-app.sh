#!/usr/bin/env bash
# Copia la aplicación a una Pi ya instalada y reinicia los servicios, sin reconstruir
# la imagen. Útil para iterar sobre el código Python durante el desarrollo.
#
#   ./scripts/deploy-app.sh                 # root@edgeai.local
#   ./scripts/deploy-app.sh root@192.168.1.50
#
# Nota: los cambios definitivos deben quedar en el repositorio para que la próxima
# imagen los incluya (la receta edgeai-helpdesk toma el código de app/).
set -euo pipefail
source "$(dirname "$0")/common.sh"

HOST="${1:-root@edgeai.local}"
APP="$REPO_ROOT/app"

info "Copiando la aplicación a $HOST"
tar -C "$APP" --exclude='__pycache__' -cf - edgeai_helpdesk | \
    ssh "$HOST" 'tar -C /usr/lib/edgeai -xf - && chown -R root:root /usr/lib/edgeai'
scp -q "$APP"/bin/edgeai-* "$HOST:/usr/bin/"
scp -q "$APP"/systemd/*.service "$HOST:/lib/systemd/system/"
scp -q "$APP/config/casos_demo.json" "$HOST:/usr/share/edgeai/"
if [ "${COPIAR_CONFIG:-0}" = "1" ]; then
    scp -q "$APP/config/helpdesk.conf" "$APP/config/categorias.json" "$HOST:/etc/edgeai/"
else
    info "Configuración de /etc/edgeai sin cambios (COPIAR_CONFIG=1 para reemplazarla)"
fi
ssh "$HOST" 'systemctl daemon-reload && systemctl restart edgeai-helpdesk edgeai-kiosk && edgeai-admin estado'
