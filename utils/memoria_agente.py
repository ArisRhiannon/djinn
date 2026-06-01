"""
MemoriaAgente — Gestor de memoria consolidada por agente.

Maneja la memoria a largo plazo, creencias persistentes y eventos recientes
de cada agente en la simulación.

ESTRUCTURA EN agente_core.json:
{
    "hash_historial": "sha256...",
    "stats": {"fuerza": 5, "agilidad": 5, "carisma": 5, "supervivencia": 5, "suerte": 5},
    "zona_actual": "bosque_norte",
    "hp": 100,
    "inventario": [],
    "memoria": {
        "creencias": ["Juan me traicionó en turno 7"],
        "eventos_recientes": [{"turno": 8, "resumen": "Ataqué a Juan..."}]
    }
}
"""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Optional

MAX_TOKENS_MEMORIA = 800
MAX_CREENCIAS = 20
MAX_EVENTOS = 10


class MemoriaAgente:
    """Gestiona la memoria consolidada de un agente."""

    def __init__(self, user_id: str, user_name: str = None, data_dir: str = "data/personas"):
        self.user_id = str(user_id)
        self.user_name = str(user_name) if user_name else str(user_id)
        self.data_dir = Path(data_dir)
        # Carpeta: user_id - nombre (ej: 123456789 - Juan)
        carpeta = f"{self.user_id} - {self.user_name}"
        self.path = self.data_dir / carpeta / "agente_core.json"
        self.data = self._cargar()

    def _cargar(self) -> dict:
        """Carga el estado del agente desde disco."""
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, IOError):
                pass
        
        # Estado por defecto
        return {
            "hash_historial": "",
            "stats": {
                "fuerza": 5,
                "agilidad": 5,
                "carisma": 5,
                "supervivencia": 5,
                "suerte": 5,
                "inteligencia": 5,
            },
            "zona_actual": "bosque_norte",
            "hp": 100,
            "inventario": [],
            "memoria": {
                "creencias": [],
                "eventos_recientes": [],
            },
        }

    def _guardar(self) -> None:
        """Guarda el estado del agente a disco."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def consolidar(self) -> str:
        """
        Genera el string de memoria para inyectar en el prompt del agente.
        Máximo ~800 tokens.
        """
        mem = self.data.get("memoria", {})
        creencias = mem.get("creencias", [])
        eventos = mem.get("eventos_recientes", [])[-5:]  # Solo últimos 5

        partes = []

        # Estado actual
        stats = self.data.get("stats", {})
        partes.append(
            f"TU ESTADO: HP={self.data.get('hp', 100)}/100 | "
            f"Zona={self.data.get('zona_actual', 'desconocido')} | "
            f"Fuerza={stats.get('fuerza', 5)} | Agilidad={stats.get('agilidad', 5)} | "
            f"Carisma={stats.get('carisma', 5)} | Supervivencia={stats.get('supervivencia', 5)} | "
            f"Suerte={stats.get('suerte', 5)} | Inteligencia={stats.get('inteligencia', 5)}"
        )

        if creencias:
            partes.append("LO QUE SABES/CREES:\n" + "\n".join(f"- {c}" for c in creencias[-MAX_CREENCIAS:]))

        if eventos:
            partes.append(
                "ÚLTIMOS TURNOS:\n" + "\n".join(
                    f"- Turno {e['turno']}: {e['resumen']}"
                    for e in eventos
                )
            )

        return "\n\n".join(partes) if partes else "Sin memoria previa."

    def actualizar_post_turno(self, turno: int, delta: dict, accion_agente: dict) -> None:
        """
        Llamar DESPUÉS de que el GM resuelve. Nunca durante decisión del agente.
        
        Args:
            turno: Número de turno actual
            delta: Dict con hp_delta, nueva_zona, item_ganado, evento_publico, muerto
            accion_agente: Dict con la acción que ejecutó el agente este turno
        """
        mem = self.data.setdefault("memoria", {"creencias": [], "eventos_recientes": []})

        # Actualizar HP
        hp_actual = self.data.get("hp", 100)
        hp_delta = delta.get("hp_delta", 0)
        self.data["hp"] = max(0, min(100, hp_actual + hp_delta))

        # Actualizar zona
        if delta.get("nueva_zona"):
            self.data["zona_actual"] = delta["nueva_zona"]

        # Agregar item
        item = delta.get("item_ganado")
        if item:
            inventario = self.data.setdefault("inventario", [])
            if item not in inventario:
                inventario.append(item)

        # Agregar evento al historial
        evento = delta.get("evento_publico", f"Turno {turno} sin eventos destacados.")
        accion = accion_agente.get("accion_tipo", "descansar")
        
        # Combinar acción + resultado
        resumen = f"[Turno {turno}] {accion.upper()}: {evento}"
        
        mem["eventos_recientes"].append({
            "turno": turno,
            "resumen": resumen,
            "accion": accion,
        })

        # Mantener solo últimos MAX_EVENTOS
        mem["eventos_recientes"] = mem["eventos_recientes"][-MAX_EVENTOS:]

        self._guardar()

    def agregar_creencia(self, creencia: str) -> None:
        """
        Para que el GM pueda inyectar creencias persistentes.
        Ej: 'Juan es hostil', 'El bunker tiene agua'.
        """
        mem = self.data.setdefault("memoria", {"creencias": [], "eventos_recientes": []})
        
        if creencia not in mem["creencias"]:
            mem["creencias"].append(creencia)
            # Máximo MAX_CREENCIAS creencias
            mem["creencias"] = mem["creencias"][-MAX_CREENCIAS:]
            self._guardar()

    def get_estado(self) -> dict:
        """Retorna el estado completo del agente."""
        return {
            "hp": self.data.get("hp", 100),
            "zona": self.data.get("zona_actual", "bosque_norte"),
            "stats": self.data.get("stats", {}),
            "inventario": self.data.get("inventario", []),
            "vivo": self.data.get("hp", 100) > 0,
        }

    def set_stats(self, stats: dict) -> None:
        """Establece los stats del agente (usado después de destilar)."""
        self.data["stats"] = stats
        self._guardar()

    def set_hash(self, hash_val: str) -> None:
        """Guarda el hash del historial para cache."""
        self.data["hash_historial"] = hash_val
        self._guardar()

    def get_hash(self) -> str:
        """Retorna el hash del historial."""
        return self.data.get("hash_historial", "")


def generar_hash_historial(mensajes: list) -> str:
    """
    Genera SHA-256 del contenido de los mensajes.
    Útil para cachear la destilación.
    """
    contenido = "\n".join(
        msg.get("content", "")[:500] for msg in mensajes
    )
    return hashlib.sha256(contenido.encode("utf-8")).hexdigest()