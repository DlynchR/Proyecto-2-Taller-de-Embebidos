# Guía paso a paso: generación e instalación de la imagen

Esta guía lleva desde un repositorio recién clonado hasta la Raspberry Pi 4 funcionando con
la mesa de ayuda. Los comandos se ejecutan desde la raíz del repositorio salvo que se indique
otra cosa.

## 0. Qué se necesita

**Máquina de build** (no es la Pi):

| Recurso | Mínimo | Recomendado |
|---|---|---|
| Sistema | Linux x86_64 (Ubuntu 22.04/24.04 o Debian 12) | — |
| Disco libre | 70 GB (con `rm_work`) | 100 GB |
| RAM | 8 GB | 16 GB o más |
| CPU | 4 núcleos | 8 o más |
| Internet | Sí: el primer build descarga ~6 GB de fuentes (incluido Ollama, ~1.5 GB) | — |

Un servidor del laboratorio sirve igual: los pasos son los mismos por SSH.

**Para la Pi:**

- Raspberry Pi 4 Model B con **4 GB** de RAM como mínimo (8 GB recomendado: los dos modelos
  ocupan ~2.5–3 GB en memoria).
- microSD de **16 GB** o más (clase A1/A2).
- Fuente USB-C de 5 V / 3 A.
- Monitor HDMI y teclado USB para el kiosco (opcional si se usa solo la web).
- Cable Ethernet o red Wi-Fi.
- Opcional: 3 LEDs con sus resistencias (ver [hardware.md](hardware.md)).

## 1. Preparar el host

```bash
sudo apt install gawk wget git diffstat unzip texinfo gcc build-essential chrpath socat \
     cpio python3 python3-pip python3-pexpect xz-utils debianutils iputils-ping python3-git \
    python3-jinja2 python3-subunit zstd liblz4-tool file locales libacl1 bmap-tools graphviz curl jq
sudo locale-gen en_US.UTF-8
```

**AppArmor:** compruebe los namespaces con el script y con una tarea real de BitBake.
No basta con leer el valor de `kernel.apparmor_restrict_unprivileged_userns`: puede
estar activado y permitir la construcción. Si BitBake falla por permisos, revise
su perfil con el administrador antes de desactivar protecciones globales.

Verifique todo con:

```bash
./scripts/check-host.sh
```

## 2. Descargar las capas y crear el directorio de build

```bash
./scripts/setup-build.sh
```

El script:

1. Prepara `openembedded-core`, `meta-yocto` y `meta-raspberrypi` de **wrynose**,
  y BitBake **2.18**, dentro de `sources/`. Usa los commits de `layers.lock`.
2. Ejecuta `oe-init-build-env` con `TEMPLATECONF=meta-edgeai/conf/templates/edgeai`, que crea
  `build/raspberrypi4-64/conf/local.conf` y `auto.conf` (MACHINE `raspberrypi4-64`,
  DISTRO `edgeai`) y `bblayers.conf` (meta, meta-poky, meta-raspberrypi, meta-edgeai).
3. Si falta `edgeai-secrets.conf`, lo crea desde el ejemplo; la configuración de demo se versiona.
4. Muestra las capas activas (`bitbake-layers show-layers`).

Para que todo el equipo compile exactamente las mismas revisiones de las capas:

```bash
./scripts/setup-build.sh --lock    # guarda los commits en layers.lock; agréguelo a git
```

Con `layers.lock` presente, los siguientes `setup-build.sh` usan esos commits.

### Usar las capas disponibles en `yocto_env`

En este equipo, `yocto_env` carga las capas de `~/taller-yocto/layers`. No cambie
su build original. Configure un archivo local `edgeai-build.env`, excluido de Git:

```bash
SOURCES_DIR="$HOME/taller-yocto/layers"
EDGEAI_CACHE_DIR="$HOME/taller-yocto/build"
EDGEAI_EXISTING_LAYERS=1
```

Ejecute `./scripts/setup-build.sh --existing`. Se comprueban los commits sin
hacer fetch, checkout ni merge sobre las capas compartidas. `--existing --lock`
registra sus revisiones cuando se decide actualizar el archivo de bloqueo.
No mezcle capas scarthgap con wrynose. Los builds EdgeAI quedan en este repositorio;
solo las descargas y `sstate-cache` se comparten con el taller.

## 3. Verificar la versión de Ollama (recomendado)

La receta usa Ollama **0.40.6**. Antes del primer build, confirme el hash del binario
directamente desde el release oficial:

```bash
./scripts/update-ollama.sh 0.40.6
```

Para usar otra versión (debe ser ≥ 0.35, que es cuando apareció `/v1/systemone`):

```bash
./scripts/update-ollama.sh 0.40.7
```

## 4. Credenciales y opciones (opcional)

Edite `edgeai-secrets.conf`:

```bitbake
EDGEAI_WIFI_SSID = "MiRed"
EDGEAI_WIFI_PSK = "mi-clave"
EDGEAI_WIFI_FALLBACK_SSID = "RedRespaldo"
EDGEAI_WIFI_FALLBACK_PSK = "clave-respaldo"
# Contraseña de root (por defecto "edgeai"):
#   openssl passwd -6 'nueva-clave'   -> escape cada $ como \$
EDGEAI_ROOT_PASSWORD_HASH = "\$6\$...\$..."
```

La red principal tiene prioridad 20 y la de respaldo prioridad 10. En la selección
de red, `wpa_supplicant` prefiere la principal; si no está disponible o falla la
autenticación puede seleccionar el respaldo. No hay un plazo fijo ni se comprueba
el acceso a Internet. Una conexión estable al respaldo no garantiza un regreso
inmediato a la principal cuando esta reaparezca. Ambas redes deben ser compatibles
con WPA-PSK y estar dentro del alcance de la Pi.

Sin ninguno de los dos SSID la Pi usa solo Ethernet. Con un cable directo a una laptop (sin router) también
funciona: ambas toman direcciones 169.254.x.x y la web queda en `http://edgeai.local`.

### Cambiar redes en una Pi ya instalada

Desde la consola local o por Ethernet, edite como root
`/etc/wpa_supplicant/wpa_supplicant-wlan0.conf`. Conserve sus opciones globales y
defina los perfiles con sus prioridades:

```ini
network={
  ssid="MiRed"
  psk="mi-clave"
  priority=20
}
network={
  ssid="RedRespaldo"
  psk="clave-respaldo"
  priority=10
}
```

La receta escribe SSID en hexadecimal y PSK derivadas, que también son válidas;
no las duplique al editar. Para aplicar y verificar:

```bash
chmod 600 /etc/wpa_supplicant/wpa_supplicant-wlan0.conf
systemctl restart wpa_supplicant@wlan0
wpa_cli -i wlan0 status
ip -4 addr show wlan0
```

El reinicio interrumpe el Wi-Fi y puede cerrar SSH. Tras cambiar de red la IP puede
cambiar. Para probar el respaldo, apague temporalmente el punto de acceso principal.
Estos cambios en la Pi no actualizan el repositorio ni las imágenes ya generadas;
los cambios de `edgeai-secrets.conf` se incorporan al reconstruir la imagen. QEMU
no incluye ninguno de los perfiles Wi-Fi.

En este proyecto de demostración, `edgeai-secrets.conf` se versiona con la configuración
Wi-Fi autorizada por el propietario. Tanto el archivo como la imagen pueden ser públicos:
quien los obtenga podrá usar la credencial para conectarse a esa red. No coloque aquí
tokens de GitHub ni credenciales de otras cuentas.

## 5. Precargar los modelos en la imagen (opcional, recomendado para la demo)

Sin esto, la Pi descarga los modelos la primera vez que tiene internet (~1.8 GB). Para que
funcione **sin internet desde el primer arranque**:

La opción automatizada no necesita instalar Ollama en el host:

```bash
./scripts/prepare-models.sh
```

Descarga los archivos fijados en `models.lock.json`, comprueba tamaño y SHA256,
reutiliza descargas completas y exporta `models/ollama-models.tar`. Conserva las
licencias de los modelos. Las descargas interrumpidas se guardan con extensión `.part`.

Alternativamente, si ya tiene los modelos descargados:

```bash
# En cualquier PC con Ollama >= 0.35 (los pesos GGUF sirven en cualquier arquitectura)
ollama pull tev1:0.8b
ollama pull qwen2.5:1.5b
python3 tools/export_models.py tev1:0.8b qwen2.5:1.5b -o models/ollama-models.tar
```

Y en `edgeai-secrets.conf`:

```bitbake
EDGEAI_PRELOAD_MODELS = "1"
```

## 6. Construir la imagen

```bash
./scripts/build-image.sh
```

Equivalente manual:

```bash
source sources/openembedded-core/oe-init-build-env build/raspberrypi4-64
bitbake edgeai-image
```

- El **primer build** compila toolchain, kernel y userspace: de 2 a 6 horas según la máquina.
  Si se interrumpe, vuelva a ejecutar el mismo comando: BitBake continúa donde quedó.
- Los siguientes builds reutilizan la caché. El tiempo depende de qué recetas cambien;
  no se garantiza una duración de minutos. Los cambios en `app/` invalidan la receta
  de la aplicación y sus dependientes.

Objetivos útiles:

```bash
./scripts/build-image.sh ollama-bin        # solo Ollama
./scripts/build-image.sh edgeai-helpdesk   # solo la aplicación
bitbake -e edgeai-image | grep ^IMAGE_INSTALL=   # qué entra en la imagen
```

**Resultado** en `build/raspberrypi4-64/tmp/deploy/images/raspberrypi4-64/`:

| Archivo | Uso |
|---|---|
| `edgeai-image-raspberrypi4-64.rootfs.wic.bz2` | imagen completa de la microSD (comprimida) |
| `edgeai-image-raspberrypi4-64.rootfs.wic.bmap` | mapa de bloques para grabar rápido con bmaptool |

## 7. Grabar la microSD

Identifique la tarjeta con `lsblk` (por ejemplo `/dev/sdb` o `/dev/mmcblk0`) y ejecute:

```bash
./scripts/flash-sd.sh /dev/sdX
```

El script se niega a escribir sobre el disco del sistema, pide confirmar escribiendo el nombre
del dispositivo, desmonta las particiones y graba con `bmaptool` (o `dd` si no está).

**Desde Windows o macOS:** copie el `.wic.bz2`, descomprímalo (7-Zip) y grábelo con
Raspberry Pi Imager → *Use custom* o con balenaEtcher.

## 8. Primer arranque

Inserte la microSD, conecte HDMI, teclado y red, y encienda la Pi.

1. systemd levanta `ollama.service` (Ollama en `127.0.0.1:11434`).
2. `edgeai-helpdesk.service` inicia la API y la web en el puerto 80.
3. `edgeai-kiosk.service` toma `tty1` y muestra el kiosco con las direcciones IP.
4. `edgeai-provision.service` verifica los modelos: si faltan y hay internet los descarga;
   luego los carga en RAM para que la primera consulta no espere. Mientras tanto el LED
   verde parpadea.

Accesos:

| Qué | Cómo |
|---|---|
| Kiosco | pantalla HDMI + teclado (tty1) |
| Web para usuarios | `http://edgeai.local` o `http://<IP>` |
| Panel del encargado | `http://edgeai.local/panel` |
| Consola de administración | `Ctrl+Alt+F2` en el teclado, usuario `root`, clave `edgeai` |
| SSH | `ssh root@edgeai.local` |

## 9. Verificar la instalación

En la Pi (por SSH o tty2):

```bash
edgeai-admin autoprueba      # configuración, BD, Ollama, modelos y LEDs
edgeai-admin estado          # servicios, modelos, LEDs y latencias
edgeai-admin leds probar     # enciende cada LED 1 s (detenga antes edgeai-helpdesk)
edgeai-bench --llm --csv /tmp/bench.csv   # casos de uso con los modelos reales
journalctl -u edgeai-helpdesk -f           # bitácora de la aplicación
```

## 10. Actualizar la aplicación sin reconstruir la imagen

Durante el desarrollo:

```bash
./scripts/deploy-app.sh root@edgeai.local
```

Copia `app/` a la Pi y reinicia los servicios. Para que el cambio quede en la próxima imagen
basta con que esté en el repositorio: la receta toma el código de `app/`.

## 11. Solución de problemas

| Síntoma | Causa probable y solución |
|---|---|
| `User namespaces are not usable by BitBake` | Revise permisos y el perfil AppArmor de BitBake: ver paso 1 |
| `Fetcher failure ... sha256sum mismatch` en `ollama-bin` | El hash no coincide con el release: `./scripts/update-ollama.sh 0.40.6` |
| `Please use a locale setting which supports UTF-8` | `sudo locale-gen en_US.UTF-8` |
| Build se detiene por disco | `BB_DISKMON_DIRS` lo frena antes de llenarlo: libere espacio y repita |
| El build se queda sin RAM (compilando gcc o el kernel) | Bajar `BB_NUMBER_THREADS` y `PARALLEL_MAKE` en `build/<maquina>/conf/local.conf` |
| `ERROR: edgeai-models: No existe .../ollama-models.tar` | Genere el archivo (paso 5) o use `EDGEAI_PRELOAD_MODELS = "0"` |
| Pantalla negra en HDMI | Conecte el monitor antes de encender; use el puerto HDMI0 (junto a la alimentación) |
| La web no abre en `edgeai.local` | Use la IP que muestra el kiosco; algunos Windows antiguos no resuelven mDNS |
| `edgeai-admin estado` dice que faltan modelos | Conecte internet y `edgeai-admin modelos asegurar --descargar` |
| Respuestas muy lentas o Ollama se reinicia | RAM insuficiente (Pi de 2 GB): use una Pi de 4/8 GB o `OLLAMA_MAX_LOADED_MODELS=1` en `/etc/default/ollama` |
| LEDs en "modo simulado" | Revise el cableado y que `/boot/config.txt` tenga las líneas `dtoverlay=gpio-led` |

## 12. Imagen QEMU y pruebas previas

```bash
MACHINE=qemuarm64 ./scripts/setup-build.sh
MACHINE=qemuarm64 ./scripts/build-image.sh
./scripts/test-qemu.sh
./scripts/run-qemu.sh
```

`test-qemu.sh` utiliza el framework `testimage` de Yocto con red SLIRP, sin crear
interfaces TAP ni requerir sudo. Comprueba SSH, servicios, autoprueba, web/API,
creación de un tiquete, persistencia tras reiniciar el sistema y benchmark simulado.
En QEMU se usa `edgeai-admin autoprueba --sin-leds`: solo omite la comprobación
de LEDs físicos; la configuración, base de datos, Ollama y modelos siguen siendo
obligatorios. En la Raspberry Pi, `edgeai-admin autoprueba` conserva todas las
comprobaciones de hardware. Las pruebas esperan que la API responda tras reiniciar.

El descubrimiento de `do_testimage` para QEMU se limita a OE-Core y `meta-edgeai`.
Las capas de compilación no cambian; las pruebas de hardware de `meta-raspberrypi`
no se importan para el emulador. El formato de arranque se fija en `ext4`, igual
que el sistema de archivos generado.

`run-qemu.sh` expone la web en `http://127.0.0.1:8080` y SSH en el puerto local 2222.
Ambos puertos deben estar libres. La imagen QEMU permite entrar como root sin clave:
es exclusivamente de pruebas y debe permanecer en una red virtual aislada. No contiene
las credenciales Wi-Fi ni modelos precargados; ejecuta el simulador de Ollama mediante
un override systemd exclusivo de QEMU. No valida inferencia real, Wi-Fi, GPIO ni HDMI.
En un host x86_64, ARM64 se ejecuta mediante emulación, sin aceleración KVM.

El kernel, rootfs ext4 y configuración de arranque quedan bajo
`build/qemuarm64/tmp/deploy/images/qemuarm64/`. Para recopilar sus artefactos:

```bash
MACHINE=qemuarm64 ./scripts/collect-artifacts.sh
```

Para ejecutar toda la secuencia, incluidos modelos, pruebas QEMU y Raspberry Pi:

```bash
./scripts/build-all.sh
```

Los resultados quedan en `artifacts/qemuarm64/` y `artifacts/raspberrypi4-64/`, con
manifiesto, revisiones, commit y `SHA256SUMS`. Las pruebas deben pasar antes de
construir Raspberry Pi. Un bloqueo de archivo evita dos ejecuciones simultáneas
del flujo completo sobre la misma caché.

## 13. GitHub Actions

El workflow `.github/workflows/ci.yml` ejecuta pruebas en GitHub y construye las
imágenes en este equipo con cada push a `main`, o por ejecución manual desde `main`.
Los PR solo ejecutan pruebas en runners alojados de GitHub. El trabajo de imágenes
también funciona en el repositorio público. La configuración Wi-Fi se toma del archivo
versionado `edgeai-secrets.conf`, sin requerir GitHub Secrets.

Para registrar este equipo:

1. Iniciar sesión en GitHub desde VS Code con la cuenta propietaria o administradora.
   También se puede usar GitHub CLI mediante `gh auth login --web`.
2. Ejecutar `./scripts/setup-runner.sh`. El script obtiene automáticamente el token
   temporal mediante la API y registra el runner; no hay que buscarlo, copiarlo ni
   escribirlo. Instala un servicio systemd de usuario etiquetado `edgeai-yocto`.
3. Opcionalmente, crear la variable de Actions `EDGEAI_CACHE_DIR` con la ruta de caché
   del host. En este equipo se puede usar `/home/dlynchr/taller-yocto/build`.

GitHub exige autenticación para registrar un runner propio, incluso en repositorios
públicos. Se automatiza la obtención del token, no se elimina ese requisito. Los tokens
de registro y de acceso no se publican. El repositorio predeterminado es
`DlynchR/Proyecto-2-Taller-de-Embebidos`; se puede cambiar con `EDGEAI_GITHUB_REPOSITORY`.

El equipo debe permanecer encendido y conectado, con la sesión del usuario activa.
Para mantener el servicio después de cerrar sesión, el administrador puede habilitar
linger para ese usuario. Compruebe el servicio con:

```bash
systemctl --user status edgeai-runner
journalctl --user -u edgeai-runner -f
```

Los builds del runner conservan su workspace y la caché; las capas de CI se guardan
en un directorio `edgeai-sources` independiente de las capas del taller. Los artefactos
se retienen siete días y pueden descargarlos quienes tengan acceso a Actions. No suba a
Git imágenes, modelos, tokens de GitHub ni directorios de trabajo de BitBake.

El permiso de push por sí solo no permite registrar runners; se necesita administración.
Hasta completar el registro, el trabajo de imágenes permanecerá en cola.

## 14. Compilaciones largas

Una vez iniciado el flujo, no necesita sondeos del asistente. Para consultar el avance
use el registro de la terminal o de Actions. Si el proceso se interrumpe, repita
`./scripts/build-all.sh`: se reutilizan las descargas completas, sstate y tareas válidas.
La generación de una nueva imagen no actualiza automáticamente una Pi ya instalada.
