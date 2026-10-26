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