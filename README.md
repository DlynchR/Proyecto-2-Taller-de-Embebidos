# Proyecto-2-Taller-de-Embebidos

Mesa de ayuda EdgeAI con API HTTP, interfaz web, kiosco de consola y clasificacion
de consultas mediante Ollama. Incluye un simulador para desarrollar y probar sin
modelos ni hardware.

## Desarrollo

Desde la raiz del repositorio, con Python 3.10 o posterior:

```bash
make test
make dev
```

La web queda en `http://127.0.0.1:8080` y el panel en
`http://127.0.0.1:8080/panel`. `make bench` ejecuta los casos de demostracion
contra el simulador. Para usar un servidor Ollama real, ejecute `make dev-real`.

## Estructura

- `app/`: aplicacion, configuracion e integracion con systemd.
- `tests/`: pruebas de API, decisiones, almacenamiento, indicadores y herramientas.
- `tools/`: simulador de Ollama y exportador de modelos descargados.
- [API HTTP](docs/api.md).

La aplicacion utiliza la biblioteca estandar de Python. ShellCheck es opcional
para `make lint`.

## Imagen Raspberry Pi 4

La capa `meta-edgeai` utiliza Yocto wrynose y BitBake 2.18. Las revisiones se fijan
en `layers.lock`; los manifiestos de los modelos se fijan en `models.lock.json`.
El build requiere un host Linux x86_64 con suficiente espacio libre y conexion
a internet para las descargas iniciales.

```bash
./scripts/check-host.sh
./scripts/setup-build.sh
./scripts/prepare-models.sh
./scripts/build-image.sh
```

`edgeai-secrets.conf` contiene la configuracion publica de demostracion: Wi-Fi
y precarga de modelos. La imagen generada contiene una credencial de acceso a
esa red. No incluya tokens de GitHub en ese archivo.

Los resultados quedan en `build/raspberrypi4-64/tmp/deploy/images/raspberrypi4-64/`.
`./scripts/flash-sd.sh /dev/sdX` permite grabar una microSD; verifique primero
el dispositivo con `lsblk`.

Para reutilizar capas wrynose existentes sin modificarlas, establezca
`SOURCES_DIR` y `EDGEAI_CACHE_DIR` en `edgeai-build.env`, y ejecute
`./scripts/setup-build.sh --existing`. Este archivo local no se versiona.