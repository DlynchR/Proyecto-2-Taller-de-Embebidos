# Capa meta-edgeai: recetas y configuración

```
meta-edgeai/
├── conf/
│   ├── layer.conf                         # registro de la capa y EDGEAI_REPO_DIR
│   ├── distro/edgeai.conf                 # distribución: poky + systemd, sin gráficos
│   └── templates/edgeai/                  # plantilla de build/conf (TEMPLATECONF)
│       ├── local.conf.sample
│       ├── bblayers.conf.sample
│       ├── conf-summary.txt
│       └── conf-notes.txt
├── recipes-ai/
│   ├── ollama/ollama-bin_0.40.6.bb        # Ollama (binario oficial arm64)
│   │   └── files/{ollama.service, ollama.env}
│   └── edgeai-models/edgeai-models_1.0.bb     # modelos precargados (opcional)
├── recipes-apps/
│   └── edgeai-helpdesk/edgeai-helpdesk_1.0.bb   # la aplicación (código en <repo>/app)
├── recipes-bsp/
│   └── bootfiles/rpi-config_%.bbappend    # overlays de LEDs y botón en config.txt
├── recipes-connectivity/
│   └── edgeai-network/                    # systemd-networkd, Wi-Fi, mDNS
└── recipes-core/
    ├── images/edgeai-image.bb             # la imagen
    └── packagegroups/packagegroup-edgeai.bb
```

## conf/layer.conf

Registra la colección `edgeai` con prioridad 10, declara compatibilidad con **wrynose** y
dependencia de `core` y `raspberrypi`. Define `EDGEAI_REPO_DIR` (la raíz del repositorio) con
expansión inmediata (`:=`), de modo que la receta de la aplicación pueda tomar el código de
`<repo>/app` sin copiarlo dentro de la capa.

## conf/distro/edgeai.conf

| Ajuste | Por qué |
|---|---|
| `require conf/distro/poky.conf` | hereda la distro de referencia |
| `INIT_MANAGER = "systemd"` | servicios, `StateDirectory`, `TTYPath` para el kiosco, networkd |
| `DISTRO_FEATURES:remove = "x11 wayland vulkan ptest ..."` | imagen de consola: menos recetas, menos espacio, build más corto |
| `PACKAGECONFIG:append:pn-systemd = " networkd resolved"` | red y nombre `edgeai.local` sin avahi |
| `DEFAULT_TIMEZONE = "America/Costa_Rica"` | hora local en bitácoras |
| `hostname:pn-base-files = "edgeai"` | nombre del equipo |
| `LICENSE_FLAGS_ACCEPTED += "synaptics-killswitch"` | permite el firmware Wi-Fi de la RPi4 |
| `RPI_KERNEL_DEVICETREE_OVERLAYS:append = " overlays/gpio-led.dtbo"` | compila y despliega el overlay de LEDs (no viene en la lista base de meta-raspberrypi) |

## Plantilla de build (conf/templates/edgeai)

`setup-build.sh` exporta `TEMPLATECONF` a este directorio antes de `oe-init-build-env`, por
lo que `build/raspberrypi4-64/conf/local.conf` nace con: `MACHINE = "raspberrypi4-64"`,
`DISTRO = "edgeai"`, `DL_DIR`/`SSTATE_DIR` fuera de `build/`, `rm_work` (ahorra decenas de
GB), `buildhistory` (dependencias y tamaños), `ENABLE_UART = "1"`, `GPU_MEM = "64"` y un
`include` opcional de `edgeai-secrets.conf` para credenciales que no deben versionarse.

## recipes-ai/ollama/ollama-bin_0.40.6.bb

- **Fuente:** `ollama-linux-arm64.tar.zst` del release oficial, con `sha256sum` fijo
  (`downloadfilename` incluye la versión para no mezclar versiones en `downloads/`).
- **`COMPATIBLE_HOST = "aarch64.*-linux"`:** solo existe binario de 64 bits.
- **Instalación:** `/usr/bin/ollama` y `/usr/lib/ollama/` **solo con backends de CPU**
  (`OLLAMA_EXCLUDE_BACKENDS` descarta CUDA, JetPack, ROCm, Vulkan y MLX: de ~1.5 GB
  comprimidos queda una fracción). Se usa `nonarch_libdir` porque Ollama busca sus
  bibliotecas en `<bin>/../lib/ollama` aunque en aarch64 `libdir` sea `/usr/lib64`.
- **Usuario de sistema `ollama`** (clase `useradd`) y `/var/lib/ollama/models` con su dueño.
- **Servicio** `ollama.service` (habilitado) que lee `/etc/default/ollama`:
  `OLLAMA_HOST=127.0.0.1:11434`, `OLLAMA_KEEP_ALIVE=24h`, `OLLAMA_MAX_LOADED_MODELS=2`,
  `OLLAMA_NUM_PARALLEL=1`, `OLLAMA_CONTEXT_LENGTH=2048`.
- **QA:** por tratarse de binarios precompilados se inhibe el *strip* y la separación de
  símbolos, `EXCLUDE_FROM_SHLIBS` evita que las `libggml` se anuncien como bibliotecas del
  sistema, y `INSANE_SKIP` documenta las verificaciones que no aplican (`libdir`, `dev-so`,
  `ldflags`, `already-stripped`, `file-rdeps`, `textrel`, `buildpaths`).

**Alternativa descartada:** compilar Ollama desde fuente. Requiere Go + CMake + ggml y que
`go mod` descargue dependencias durante `do_compile`, lo que choca con el modelo de fetch de
Yocto (red deshabilitada fuera de `do_fetch`) y alarga el build en horas. Con el binario
oficial el resultado es igual de reproducible gracias al hash.

## recipes-apps/edgeai-helpdesk/edgeai-helpdesk_1.0.bb

- `FILESEXTRAPATHS:prepend := "${EDGEAI_REPO_DIR}:"` + `SRC_URI = "file://app"`: el fetcher
  copia `<repo>/app` y calcula su checksum; cualquier cambio en el código reconstruye la receta.
- `allarch`: es Python puro, un solo paquete sirve a cualquier arquitectura.
- `useradd`: crea el usuario `edgeai` (sin shell, sin home interactivo). La regla udev le da
  escritura a los LEDs. **Nada corre como root.**
- Instala: `/usr/lib/edgeai/edgeai_helpdesk/` (código + web), `/usr/bin/edgeai-*`,
  `/etc/edgeai/{helpdesk.conf,categorias.json}` (`CONFFILES`), `/usr/share/edgeai/casos_demo.json`,
  tres servicios systemd, `/etc/udev/rules.d/90-edgeai.rules` y `/etc/sysctl.d/90-edgeai.conf`.
- Servicios habilitados:
  - `edgeai-helpdesk.service`: API + web en el puerto 80 con `AmbientCapabilities=CAP_NET_BIND_SERVICE`,
    `ProtectSystem=full`, `NoNewPrivileges`.
  - `edgeai-kiosk.service`: kiosco en `tty1` (`TTYPath`); la receta enmascara `getty@tty1` para que nadie más tome esa consola.
  - `edgeai-provision.service`: asegura/descarga y precarga los modelos; reintenta cada minuto
    si no hay red.
- `RDEPENDS`: `python3-core python3-modules python3-sqlite3 iproute2 kbd kbd-keymaps`.

## recipes-ai/edgeai-models/edgeai-models_1.0.bb

Extrae `models/ollama-models.tar` (creado con `tools/export_models.py`) en
`/var/lib/ollama/models` con dueño `ollama`. La imagen lo incluye solo si
`EDGEAI_PRELOAD_MODELS = "1"`. `do_install[file-checksums]` hace que un tar nuevo dispare la
reconstrucción.

## recipes-connectivity/edgeai-network/edgeai-network_1.0.bb

- `10-eth0.network`: DHCP y, si no hay servidor DHCP, **dirección link-local**: una laptop
  conectada directo por cable alcanza `http://edgeai.local`.
- `20-wlan0.network` + `wpa_supplicant-wlan0.conf` generado desde `EDGEAI_WIFI_SSID/PSK`
  (solo si se definieron) y el servicio `wpa_supplicant@wlan0` habilitado.
- `resolved.conf.d/edgeai-mdns.conf`: `MulticastDNS=yes` para publicar `edgeai.local`.

## recipes-bsp/bootfiles/rpi-config_%.bbappend

Agrega a `RPI_EXTRA_CONFIG` (que la receta `rpi-config` escribe al final de `config.txt`):

```
dtoverlay=gpio-led,gpio=17,label=edgeai-verde
dtoverlay=gpio-led,gpio=27,label=edgeai-amarillo
dtoverlay=gpio-led,gpio=22,label=edgeai-rojo
```

Solo aplica con `DISTRO = "edgeai"` (override `:edgeai`). Los valores por defecto de los pines están en `conf/distro/edgeai.conf` y se cambian con `EDGEAI_GPIO_*` en `local.conf`.

## recipes-core/packagegroups/packagegroup-edgeai.bb

`packagegroup-edgeai` (Ollama, app, red) y `packagegroup-edgeai-tools` (sqlite3, curl,
tzdata, iw, procps, util-linux, less, vim-tiny y el firmware Wi-Fi). `PACKAGE_ARCH` es de
máquina porque depende de paquetes propios de la placa.

## recipes-core/images/edgeai-image.bb

- `inherit core-image extrausers`; `IMAGE_FEATURES += "ssh-server-openssh allow-root-login"`.
- `IMAGE_INSTALL = packagegroup-core-boot + packagegroup-edgeai` (+ `edgeai-models` opcional).
- `IMAGE_ROOTFS_EXTRA_SPACE = 6 GiB` para descargar modelos en la Pi.
- `IMAGE_FSTYPES = "wic.bz2 wic.bmap"`: imagen de tarjeta lista para `bmaptool`.
- Contraseña de root por hash (`EXTRA_USERS_PARAMS`), reemplazable desde `edgeai-secrets.conf`.
- `COMPATIBLE_MACHINE = "^raspberrypi4-64$"`.
