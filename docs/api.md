# API HTTP de la mesa de ayuda

Servidor: `edgeai-helpdesk` en el puerto 80 de la Pi (8080 en desarrollo). JSON en UTF-8.
Errores: `{"error": "mensaje"}` con el código HTTP correspondiente.

## Público (kiosco y web)

### `POST /api/tickets`

Registra una consulta. La clasificación con el modelo de decisión es inmediata; la respuesta
del LLM llega después.

```json
{"texto": "Sale humo del tomacorriente de la mesa 2", "nombre": "Ana", "contacto": "ana@estudiantec.cr"}
```

`texto` es obligatorio (5 a 2000 caracteres). Respuesta `201`: el tiquete completo,
incluida la `clave` para consultarlo después.

```json
{
  "id": 14, "categoria": "infraestructura", "categoria_conf": 0.83,
  "categoria_probs": {"infraestructura": 0.94, "soporte_tecnico": 0.03, "...": 0.03},
  "urgencia_score": 2.71, "urgencia_nivel": 3,
  "en_alcance": 0.93, "apropiado": 0.97, "datos_sensibles": 0.05, "autoservicio": 0.2,
  "estado": "en_cola", "revision_manual": false, "motivo": "Urgencia alta",
  "respuesta": "", "respuesta_estado": "pendiente",
  "lat_decision_ms": 1840.2, "modelo_decision": "tev1:0.8b", "clave": "q3Jt9xZ1aBc"
}
```

### `GET /api/consulta/{id}?clave=...`

Estado y respuesta de un tiquete propio (sin texto ni datos de contacto).
`respuesta_estado`: `pendiente` · `generando` · `lista` · `error` · `omitida`.

### `GET /api/dominio`

Nombre del servicio, etiquetas de categorías, niveles de urgencia y nombres de estados.

## Panel de atención

Si `panel_token` está definido en `helpdesk.conf`, estas rutas exigen el encabezado
`X-Panel-Token`.

| Método y ruta | Descripción |
|---|---|
| `GET /api/health` | salud de Ollama, modelos faltantes, LEDs, estadísticas y latencias |
| `GET /api/cola` | tiquetes `en_cola` ordenados por urgencia y antigüedad |
| `GET /api/tickets?estado=&limit=` | listado (más recientes primero, `limit` ≤ 500) |
| `GET /api/tickets/{id}` | tiquete completo |
| `POST /api/tickets/{id}/atender` | `en_cola`/`autoservicio` → `atendido` (409 si no aplica) |
| `POST /api/tickets/{id}/reabrir` | `atendido`/`autoservicio` → `en_cola` |
| `POST /api/atender-siguiente` | atiende el tiquete más prioritario de la cola |

## Páginas

| Ruta | Contenido |
|---|---|
| `/` | formulario de consulta |
| `/panel` | tablero del encargado: cola, probabilidades, respuestas, LEDs (reales o simulados) |

## Llamada al modelo de decisión (referencia)

Lo que `decision.py` envía a Ollama en cada consulta:

```json
POST http://127.0.0.1:11434/v1/systemone
{
  "model": "tev1:0.8b",
  "state": {"servicio": "...", "que_atiende": "...", "mensaje_del_usuario": "..."},
  "questions": {
    "categoria":       {"type": "choice", "instructions": "...", "criteria": {"soporte_tecnico": "...", "...": "..."}},
    "urgencia":        {"type": "score",  "instructions": "...", "criteria": ["baja: ...", "media: ...", "alta: ...", "crítica: ..."]},
    "en_alcance":      {"type": "noul",   "instructions": "..."},
    "apropiado":       {"type": "noul",   "instructions": "...", "criteria": {"true": "...", "false": "..."}},
    "datos_sensibles": {"type": "noul",   "instructions": "..."},
    "autoservicio":    {"type": "noul",   "instructions": "..."}
  },
  "keep_alive": "24h"
}
```

Las preguntas y categorías salen de `/etc/edgeai/categorias.json`.
