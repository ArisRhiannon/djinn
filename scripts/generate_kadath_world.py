"""Generador del mundo Kadath.

Produce data/kadath_world.json desde bloques Python legibles.
Filosofía: el autor (LLM/humano) escribe el blueprint en Python estructurado;
este script lo serializa a JSON que el runtime consumirá de forma determinista.

Uso:
    python3 scripts/generate_kadath_world.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = PROJECT_ROOT / "data" / "kadath_world.json"


# ─── Helpers de construcción ─────────────────────────────────────────────────

def N(
    node_id: str,
    *,
    zone: str,
    text: str,
    act: int = 1,
    paths: Optional[List[Dict[str, Any]]] = None,
    on_enter: Optional[Dict[str, int]] = None,
    character_dialogue: Optional[Dict[str, str]] = None,
    class_bonus: Optional[Dict[str, str]] = None,
    ability_hints: Optional[Dict[str, str]] = None,
    give_item: Any = None,
    consume_item: Any = None,
    set_flags: Optional[List[str]] = None,
    clear_flags: Optional[List[str]] = None,
    hidden_paths: Optional[List[Dict[str, Any]]] = None,
    fallback_target: Optional[str] = None,
    tone: Optional[str] = None,
    primary_npc: Optional[str] = None,
    hostile_npc: Optional[str] = None,
    is_ally_npc: bool = False,
    trade: Optional[Dict[str, str]] = None,
    close_contract: Optional[str] = None,
    npc_trust: Optional[Dict[str, int]] = None,
    is_start: bool = False,
    is_ending: bool = False,
    ending_requires: Optional[Dict[str, Any]] = None,
    ending_priority: int = 50,
    force_ending_if: Optional[Dict[str, Any]] = None,
    forced_ending_target: Optional[str] = None,
    embed_image: Optional[str] = None,
    text_variants: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Construye un nodo del mundo con valores por defecto razonables."""
    node: Dict[str, Any] = {
        "id": node_id,
        "zone": zone,
        "text": text,
        "act": act,
        "paths": paths or [],
        "on_enter": on_enter or {},
        "character_dialogue": character_dialogue or {},
        "class_bonus": class_bonus or {},
        "ability_hints": ability_hints or {},
        "is_ending": is_ending,
    }
    if is_start:
        node["is_start"] = True
    if give_item is not None:
        node["give_item"] = give_item
    if consume_item is not None:
        node["consume_item"] = consume_item
    if set_flags:
        node["set_flags"] = set_flags
    if clear_flags:
        node["clear_flags"] = clear_flags
    if hidden_paths:
        node["hidden_paths"] = hidden_paths
    if fallback_target:
        node["fallback_target"] = fallback_target
    if tone:
        node["tone"] = tone
    if primary_npc:
        node["primary_npc"] = primary_npc
    if hostile_npc:
        node["hostile_npc"] = hostile_npc
    if is_ally_npc:
        node["is_ally_npc"] = True
    if trade:
        node["trade"] = trade
    if close_contract:
        node["close_contract"] = close_contract
    if npc_trust:
        node["npc_trust"] = npc_trust
    if ending_requires:
        node["ending_requires"] = ending_requires
    if is_ending:
        node["ending_priority"] = ending_priority
    if force_ending_if:
        node["force_ending_if"] = force_ending_if
    if forced_ending_target:
        node["forced_ending_target"] = forced_ending_target
    if embed_image:
        node["embed_image"] = embed_image
    if text_variants:
        node["text_variants"] = text_variants
    return node


def P(
    label: str,
    target: str,
    *,
    style: str = "primary",
    conditions: Optional[Dict[str, Any]] = None,
    effects: Optional[Dict[str, int]] = None,
    show_locked: bool = False,
    consume_item: Optional[str] = None,
    give_item: Optional[str] = None,
    set_flags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Construye una arista (path) con o sin condiciones y efectos propios.

    Los campos consume_item/give_item/set_flags permiten que la arista haga
    efectos SOLO si se toma esa salida, independientemente del nodo destino.
    """
    path: Dict[str, Any] = {"label": label, "target": target, "style": style}
    if conditions:
        path["conditions"] = conditions
    if effects:
        path["effects"] = effects
    if show_locked:
        path["show_locked"] = True
    if consume_item:
        path["consume_item"] = consume_item
    if give_item:
        path["give_item"] = give_item
    if set_flags:
        path["set_flags"] = set_flags
    return path


# ─── Registros de construcción ───────────────────────────────────────────────

WORLD: Dict[str, Dict[str, Any]] = {}


def register(node: Dict[str, Any]) -> None:
    nid = node["id"]
    if nid in WORLD:
        raise ValueError(f"Nodo duplicado: {nid}")
    WORLD[nid] = node


# Placeholders que completarán los módulos de cada acto (se cargan abajo).
# Para mantener este archivo ordenado, cada acto vive en su propio módulo
# dentro de scripts/kadath/.


def build_world() -> Dict[str, Dict[str, Any]]:
    """Llama a los builders de cada acto en orden y devuelve WORLD."""
    from kadath_acts import (  # type: ignore
        build_prologue,
        build_act2,
        build_act3,
        build_act4,
        build_act5,
        build_endings,
    )
    from kadath_act1_rework import build_act1_rework  # type: ignore

    for builder in (
        build_prologue,
        build_act1_rework,  # Rework: Edyssey + Payaso (57 nodos)
        build_act2,
        build_act3,
        build_act4,
        build_act5,
        build_endings,
    ):
        for node in builder(N, P):
            register(node)

    # Patch prólogo: apuntar al nuevo act1_descenso_inicio
    if "prologo_despertar" in WORLD:
        WORLD["prologo_despertar"]["paths"] = [
            P("Descender hacia la voz", "act1_descenso_inicio",
              style="primary", effects={"lucidez": 2}),
            P("Quedarte en el umbral, escuchando", "act1_descenso_inicio",
              style="secondary", effects={"memoria": 3, "voluntad": 2}),
            P("Lanzarte al vacío lateral", "act1_descenso_caida",
              style="danger", effects={"voluntad": -4, "lore": 3}),
        ]

    # Arco de la Isla de Papu (12 nodos)
    from kadath_arc_isla_papu import build_arc_isla_papu  # type: ignore
    for node in build_arc_isla_papu(N, P):
        register(node)

    # Profundización: inyectar text_variants a nodos clave
    from kadath_text_variants import apply_text_variants  # type: ignore
    injected = apply_text_variants(WORLD)
    print(f"ℹ️  Inyectados {injected} text_variants en nodos clave")

    return WORLD


def validate(world: Dict[str, Dict[str, Any]]) -> List[str]:
    """Valida integridad del grafo. Devuelve lista de errores."""
    errors: List[str] = []
    ids = set(world.keys())

    # Debe haber exactamente un nodo is_start.
    starts = [nid for nid, n in world.items() if n.get("is_start")]
    if len(starts) == 0:
        errors.append("No hay nodo is_start")
    elif len(starts) > 1:
        errors.append(f"Múltiples nodos is_start: {starts}")

    # Todos los targets deben existir
    for nid, n in world.items():
        for p in n.get("paths", []) or []:
            t = p.get("target")
            if t and t not in ids:
                errors.append(f"Nodo '{nid}': target roto '{t}'")
        for hp in n.get("hidden_paths", []) or []:
            t = hp.get("target")
            if t and t not in ids:
                errors.append(f"Nodo '{nid}' (hidden): target roto '{t}'")
        ft = n.get("fallback_target")
        if ft and ft not in ids:
            errors.append(f"Nodo '{nid}': fallback_target roto '{ft}'")
        fet = n.get("forced_ending_target")
        if fet and fet not in ids:
            errors.append(f"Nodo '{nid}': forced_ending_target roto '{fet}'")

    # Debe haber al menos 10 endings
    endings = [nid for nid, n in world.items() if n.get("is_ending")]
    if len(endings) < 10:
        errors.append(f"Solo {len(endings)} endings; se esperaban >=10")

    # Hardlocks: nodos donde TODAS las rutas son condicionales y no hay fallback
    # El runtime tiene un plan B automático, pero preferimos detectarlo en build.
    for nid, n in world.items():
        if n.get("is_ending"):
            continue
        paths = n.get("paths", []) or []
        if not paths:
            continue
        all_conditional = all(bool(p.get("conditions")) for p in paths)
        has_unconditional = not all_conditional
        has_fallback = bool(n.get("fallback_target"))
        if all_conditional and not has_fallback:
            # warning, no error fatal: el runtime tiene plan B
            errors.append(
                f"WARN hardlock posible en '{nid}': todas las rutas "
                f"condicionales y sin fallback_target"
            )

    return errors


def main() -> None:
    # Necesitamos que el dir de este script esté en sys.path para importar kadath_acts.
    import sys
    sys.path.insert(0, str(Path(__file__).parent))

    world = build_world()
    issues = validate(world)
    warnings = [i for i in issues if i.startswith("WARN")]
    errors = [i for i in issues if not i.startswith("WARN")]

    if warnings:
        print("⚠️  WARNINGS:")
        for w in warnings:
            print(f"  - {w}")
    if errors:
        print("❌ ERRORES DE VALIDACIÓN:")
        for e in errors:
            print(f"  - {e}")
        raise SystemExit(1)

    # Escribe el JSON
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(world, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    endings = [nid for nid, n in world.items() if n.get("is_ending")]
    print(f"✅ Escrito {OUT_PATH}")
    print(f"   {len(world)} nodos totales")
    print(f"   {len(endings)} finales: {endings}")


if __name__ == "__main__":
    main()
