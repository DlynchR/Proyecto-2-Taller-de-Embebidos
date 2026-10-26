# Guion de la demostración y casos de uso

Demostración presencial (K1-420, semana del 9 de noviembre). El instructivo pide mostrar la
aplicación, el flujo de síntesis del sistema operativo y la descripción de la aplicación y
de las recetas. Duración sugerida: 15 minutos.

## Lista de verificación previa (el día anterior)

- [ ] Imagen construida desde el repositorio limpio (`git status` sin cambios) y grabada.
- [ ] Modelos **precargados** en la imagen (`EDGEAI_PRELOAD_MODELS = "1"`): la demo no debe
      depender del internet del aula.
- [ ] `edgeai-admin autoprueba` sin fallos en la Pi.
- [ ] `edgeai-bench --llm --csv bench.csv` ejecutado en la Pi; guardar el CSV y la salida
      (latencias reales para la presentación).
- [ ] Laptop con el panel abierto en `http://edgeai.local/panel` (cable Ethernet directo
      funciona sin router).
- [ ] Monitor, teclado y protoboard con los LEDs probados (`edgeai-admin leds probar`).
- [ ] Terminal en la máquina de build con `build/` listo para mostrar BitBake.
- [ ] Base de tiquetes vacía: `systemctl stop edgeai-helpdesk && rm /var/lib/edgeai/tickets.db* && systemctl start edgeai-helpdesk`.

## Guion

| Min | Parte | Qué mostrar |
|---|---|---|
| 0–2 | Problema y solución | Mesa de ayuda local: JEV decide, el LLM redacta, nada sale de la Pi ([arquitectura.md](arquitectura.md)) |
| 2–6 | Síntesis del SO | ver abajo |
| 6–12 | Casos de uso en vivo | ver tabla de casos |
| 12–14 | Robustez | Ollama caído, sin red |
| 14–15 | Resultados | salida de `edgeai-bench`: aciertos y latencias JEV vs LLM |

### Flujo de síntesis del sistema operativo (en la máquina de build)

```bash
source sources/openembedded-core/oe-init-build-env build/raspberrypi4-64
bitbake-layers show-layers                       # 4 capas: core, poky, raspberrypi, edgeai
bitbake-layers show-recipes 'edgeai*' 'ollama*'  # recetas propias
bitbake-layers show-appends | grep -A1 rpi-config
cat ../meta-edgeai/recipes-ai/ollama/ollama-bin_0.40.6.bb
bitbake -e edgeai-image | grep ^IMAGE_INSTALL=
bitbake edgeai-helpdesk -c cleansstate && bitbake edgeai-image   # cambio en app/ → solo se rehace lo necesario
ls -lh tmp/deploy/images/raspberrypi4-64/*.wic.bz2
```

Mostrar `docs/generated/edgeai-runtime-deps.svg` (de `./scripts/dependency-graph.sh`) y
`grep edgeai /boot/config.txt` en la Pi para enlazar la receta con el resultado.

### Casos de uso (los mismos de `casos_demo.json`)

| Caso | Texto a escribir | Resultado esperado | Qué señalar |
|---|---|---|---|
| CU-01 | La computadora de la mesa 4 no enciende, ya revisé el cable y nada. | soporte técnico, urgencia media, en cola | LED amarillo; respuesta con pasos de la base de conocimiento |
| CU-02 | ¿Cómo me conecto a la red inalámbrica del laboratorio con mi laptop? | autoservicio | no ocupa la cola; el LLM da los pasos |
| CU-03 | Necesito que me presten un kit de Raspberry Pi para el proyecto, ¿qué ocupo? | préstamo de equipo | respuesta con requisitos (carné, plazo) |
| CU-05 | Sale humo y huele a quemado en el tomacorriente de la mesa 2, hay estudiantes trabajando. | infraestructura, **crítica** | LED rojo; queda primero en la cola |
| CU-08 | No puedo entrar a la computadora, mi usuario es ana.mora y mi contraseña es Tec2026*... | soporte técnico, **datos sensibles** | etiqueta en el panel; la respuesta pide no compartir contraseñas |
| CU-09 | ¿Me recomiendan una receta fácil de arroz con pollo? | fuera de alcance | plantilla inmediata: **no se usa el LLM** |
| CU-10 | (mensaje con insultos) | rechazado | moderación sin LLM |

En el panel, abrir un tiquete para mostrar las **probabilidades** de cada categoría y las
cuatro preguntas sí/no: es la salida tipada del modelo de decisión, y las dos latencias
(decisión vs. redacción) muestran por qué JEV va primero.

### Robustez

```bash
systemctl stop ollama       # LED rojo parpadea; un tiquete nuevo entra igual como "sin_clasificar" + revisión manual
systemctl start ollama      # vuelve a verde; el sistema se recupera solo
```

- Desconectar el cable de red: el kiosco sigue funcionando (todo es local).
- En el panel, "Atender siguiente": el tiquete crítico pasa a "atendido" y el LED rojo se apaga.

## Verificación con casos de uso (`edgeai-bench`)

```bash
edgeai-bench --llm --csv /tmp/bench.csv
```

Para cada caso compara estado, categoría, urgencia (±1 nivel) y datos sensibles contra lo
esperado en `casos_demo.json`, y reporta latencia promedio, p50 y p95 de la decisión y de la
redacción. Los números de la Pi real son los que van a la presentación y a la bitácora.
Si algún caso falla de forma sistemática, el ajuste se hace en `categorias.json` (redacción
de preguntas y descripciones) o en los umbrales de `helpdesk.conf`, y se vuelve a medir.

## Si algo sale mal

| Problema | Respuesta rápida |
|---|---|
| La primera consulta tarda mucho | los modelos no estaban en RAM: `edgeai-admin modelos precargar` antes de empezar |
| El kiosco no aparece | `Ctrl+Alt+F1`; `systemctl restart edgeai-kiosk` |
| No abre `edgeai.local` | usar la IP que muestra el kiosco |
| Respuesta del LLM rara | se muestra igual la decisión (que es lo que importa); se puede bajar `llm_temperatura` |
