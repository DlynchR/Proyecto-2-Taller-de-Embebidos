"""Persistencia local de tiquetes en SQLite."""

from __future__ import annotations

import csv
import json
import os
import secrets
import sqlite3
import threading
from datetime import datetime, timedelta, timezone

from .decision import ATENDIDO, AUTOSERVICIO, EN_COLA, Decision

SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    creado           TEXT NOT NULL,
    actualizado      TEXT NOT NULL,
    nombre           TEXT,
    contacto         TEXT,
    texto            TEXT NOT NULL,
    categoria        TEXT NOT NULL,
    categoria_conf   REAL,
    categoria_probs  TEXT,
    urgencia_score   REAL,
    urgencia_nivel   INTEGER,
    en_alcance       REAL,
    apropiado        REAL,
    datos_sensibles  REAL,
    autoservicio     REAL,
    estado           TEXT NOT NULL,
    revision_manual  INTEGER DEFAULT 0,
    motivo           TEXT,
    respuesta        TEXT,
    respuesta_estado TEXT NOT NULL DEFAULT 'pendiente',
    resumen          TEXT,
    lat_decision_ms  REAL,
    lat_llm_ms       REAL,
    modelo_decision  TEXT,
    modelo_llm       TEXT,
    error            TEXT,
    atendido_en      TEXT,
    clave            TEXT
);
CREATE INDEX IF NOT EXISTS idx_tickets_estado ON tickets(estado);
"""

# respuesta_estado: pendiente -> generando -> lista | error | omitida
PENDIENTE, GENERANDO, LISTA, ERROR, OMITIDA = "pendiente", "generando", "lista", "error", "omitida"

PUBLIC_FIELDS = (
    "id", "creado", "actualizado", "nombre", "categoria", "categoria_conf",
    "categoria_probs", "urgencia_score", "urgencia_nivel", "en_alcance",
    "apropiado", "datos_sensibles", "autoservicio", "estado", "revision_manual",
    "motivo", "respuesta", "respuesta_estado", "resumen", "lat_decision_ms",
    "lat_llm_ms", "modelo_decision", "modelo_llm", "atendido_en", "texto",
    "contacto", "error", "clave",
)

# Vista pública para quien hizo la consulta (kiosco): sin datos de terceros.
CONSULTA_FIELDS = (
    "id", "creado", "categoria", "urgencia_nivel", "estado", "respuesta",
    "respuesta_estado", "lat_decision_ms", "lat_llm_ms",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class TicketStore:
    def __init__(self, path: str):
        self.path = path
        if path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        with self._lock:
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.executescript(SCHEMA)
            self._db.commit()

    def close(self) -> None:
        with self._lock:
            self._db.close()

    # --------------------------------------------------------------- escritura
    def create(self, texto: str, decision: Decision, nombre: str = "", contacto: str = "",
               respuesta: str = "", respuesta_estado: str = PENDIENTE) -> int:
        ts = now_iso()
        with self._lock:
            cur = self._db.execute(
                """INSERT INTO tickets (creado, actualizado, nombre, contacto, texto, categoria,
                   categoria_conf, categoria_probs, urgencia_score, urgencia_nivel, en_alcance,
                   apropiado, datos_sensibles, autoservicio, estado, revision_manual, motivo,
                   respuesta, respuesta_estado, lat_decision_ms, modelo_decision, clave)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    ts, ts, nombre, contacto, texto, decision.categoria, decision.categoria_conf,
                    json.dumps(decision.categoria_probs), decision.urgencia_score,
                    decision.urgencia_nivel, decision.en_alcance, decision.apropiado,
                    decision.datos_sensibles, decision.autoservicio, decision.estado,
                    int(decision.revision_manual), decision.motivo, respuesta, respuesta_estado,
                    decision.latencia_ms, decision.modelo, secrets.token_urlsafe(8),
                ),
            )
            self._db.commit()
            return int(cur.lastrowid)

    def update(self, ticket_id: int, **fields) -> None:
        if not fields:
            return
        fields["actualizado"] = now_iso()
        cols = ", ".join(f"{k} = ?" for k in fields)
        with self._lock:
            self._db.execute(f"UPDATE tickets SET {cols} WHERE id = ?", (*fields.values(), ticket_id))
            self._db.commit()

    def mark_attended(self, ticket_id: int) -> bool:
        ts = now_iso()
        with self._lock:
            cur = self._db.execute(
                "UPDATE tickets SET estado = ?, atendido_en = ?, actualizado = ? WHERE id = ? AND estado IN (?, ?)",
                (ATENDIDO, ts, ts, ticket_id, EN_COLA, AUTOSERVICIO),
            )
            self._db.commit()
            return cur.rowcount > 0

    def reopen(self, ticket_id: int) -> bool:
        with self._lock:
            cur = self._db.execute(
                "UPDATE tickets SET estado = ?, atendido_en = NULL, actualizado = ? WHERE id = ? AND estado IN (?, ?)",
                (EN_COLA, now_iso(), ticket_id, ATENDIDO, AUTOSERVICIO),
            )
            self._db.commit()
            return cur.rowcount > 0

    def purge(self, days: int) -> int:
        limite = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
        with self._lock:
            cur = self._db.execute("DELETE FROM tickets WHERE creado < ?", (limite,))
            self._db.commit()
            return cur.rowcount

    # ---------------------------------------------------------------- lectura
    @staticmethod
    def _row(row: sqlite3.Row | None) -> dict | None:
        if row is None:
            return None
        data = {k: row[k] for k in PUBLIC_FIELDS}
        data["categoria_probs"] = json.loads(data["categoria_probs"] or "{}")
        data["revision_manual"] = bool(data["revision_manual"])
        return data

    def get(self, ticket_id: int) -> dict | None:
        with self._lock:
            row = self._db.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        return self._row(row)

    def list(self, estado: str | None = None, limit: int = 100) -> list[dict]:
        sql = "SELECT * FROM tickets"
        args: tuple = ()
        if estado:
            sql += " WHERE estado = ?"
            args = (estado,)
        sql += " ORDER BY id DESC LIMIT ?"
        with self._lock:
            rows = self._db.execute(sql, (*args, limit)).fetchall()
        return [self._row(r) for r in rows]

    def queue(self) -> list[dict]:
        """Cola de atención ordenada por urgencia y luego por antigüedad."""
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM tickets WHERE estado = ? ORDER BY urgencia_score DESC, id ASC",
                (EN_COLA,),
            ).fetchall()
        return [self._row(r) for r in rows]

    def pending_replies(self) -> list[int]:
        with self._lock:
            rows = self._db.execute(
                "SELECT id FROM tickets WHERE respuesta_estado IN (?, ?) ORDER BY id",
                (PENDIENTE, GENERANDO),
            ).fetchall()
        return [int(r["id"]) for r in rows]

    def stats(self, nivel_urgente: int) -> dict:
        with self._lock:
            por_estado = {
                r["estado"]: r["n"]
                for r in self._db.execute("SELECT estado, COUNT(*) AS n FROM tickets GROUP BY estado")
            }
            urgentes = self._db.execute(
                "SELECT COUNT(*) FROM tickets WHERE estado = ? AND urgencia_nivel >= ?",
                (EN_COLA, nivel_urgente),
            ).fetchone()[0]
            lat = self._db.execute(
                """SELECT AVG(lat_decision_ms), MAX(lat_decision_ms),
                          AVG(lat_llm_ms), MAX(lat_llm_ms), COUNT(lat_llm_ms)
                   FROM tickets WHERE lat_decision_ms > 0"""
            ).fetchone()
            generando = self._db.execute(
                "SELECT COUNT(*) FROM tickets WHERE respuesta_estado IN (?, ?)", (PENDIENTE, GENERANDO)
            ).fetchone()[0]
        return {
            "por_estado": por_estado,
            "total": sum(por_estado.values()),
            "en_cola": por_estado.get(EN_COLA, 0),
            "urgentes": urgentes,
            "respuestas_pendientes": generando,
            "decision_ms_promedio": round(lat[0], 1) if lat[0] else None,
            "decision_ms_max": round(lat[1], 1) if lat[1] else None,
            "llm_ms_promedio": round(lat[2], 1) if lat[2] else None,
            "llm_ms_max": round(lat[3], 1) if lat[3] else None,
            "respuestas_generadas": lat[4],
        }

    def export_csv(self, path: str) -> int:
        with self._lock:
            rows = self._db.execute("SELECT * FROM tickets ORDER BY id").fetchall()
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            if rows:
                writer.writerow(rows[0].keys())
            for row in rows:
                writer.writerow(list(row))
        return len(rows)
