"""
Template Engine — Renderizado ultra-rápido de gráficos SVG con Jinja2.

Reemplaza la generación LLM de SVGs (20-45s) con templates pre-construidos
que aceptan datos JSON (~50ms render + ~50ms cairosvg = <100ms total).

Templates disponibles:
    tierlist, leaderboard, bar_chart, profile_card, banner,
    donut_chart, stat_grid, comparison
"""
from __future__ import annotations

import io
import json
import logging
import math
from pathlib import Path
from typing import Any

import cairosvg
from jinja2 import Environment, FileSystemLoader, select_autoescape

log = logging.getLogger("template_engine")

# ── Directorio base ──────────────────────────────────────────────────────
_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


# ── Schemas mínimos de validación ────────────────────────────────────────
_SCHEMAS: dict[str, dict[str, list[str]]] = {
    "tierlist": {
        "required": ["title", "tiers"],
        "optional": ["subtitle", "watermark"],
    },
    "leaderboard": {
        "required": ["title", "rows"],
        "optional": ["subtitle", "period"],
    },
    "bar_chart": {
        "required": ["title", "bars"],
        "optional": ["subtitle", "max_value", "y_labels"],
    },
    "profile_card": {
        "required": ["name"],
        "optional": ["initials", "badge", "tag_role", "stats",
                      "xp_current", "xp_total"],
    },
    "banner": {
        "required": ["title"],
        "optional": ["icon", "description", "details", "badge"],
    },
    "donut_chart": {
        "required": ["title", "segments"],
        "optional": ["subtitle", "center_text", "center_label"],
    },
    "stat_grid": {
        "required": ["title", "stats"],
        "optional": ["subtitle"],
    },
    "comparison": {
        "required": ["title", "left", "right"],
        "optional": ["subtitle", "stat_labels"],
    },
    "radar_chart": {
        "required": ["title", "axes"],
        "optional": ["subtitle"],
    },
    "timeline": {
        "required": ["title", "events"],
        "optional": ["subtitle"],
    },
    "heatmap": {
        "required": ["title", "data"],
        "optional": ["day_labels", "hour_labels"],
    },
    "achievement_card": {
        "required": ["title", "icon"],
        "optional": ["description", "date", "progress"],
    },
    "love_graph": {
        "required": ["ships"],
        "optional": ["title"],
    },
    "graph_network": {
        "required": ["title", "nodes", "edges"],
        "optional": ["subtitle", "max_weight", "max_msgs"],
    },
    "correlation_matrix": {
        "required": ["title", "users", "matrix"],
        "optional": ["subtitle"],
    },
    "investigation_timeline": {
        "required": ["title", "events"],
        "optional": ["subtitle"],
    },
}


class TemplateEngine:
    """Motor de templates SVG con Jinja2 + cairosvg."""

    def __init__(self, template_dir: Path | str | None = None):
        td = Path(template_dir) if template_dir else _TEMPLATE_DIR
        if not td.is_dir():
            raise FileNotFoundError(f"Template directory not found: {td}")

        self._env = Environment(
            loader=FileSystemLoader(str(td)),
            autoescape=select_autoescape(default=True),
            keep_trailing_newline=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        # Custom filters
        self._env.filters["clamp"] = lambda v, lo, hi: max(lo, min(hi, v))
        self._env.filters["pct"] = lambda v, mx: (v / mx * 100) if mx > 0 else 0
        self._env.filters["bar_px"] = lambda v, mx, w: int((v / mx) * w) if mx > 0 else 0
        self._env.filters["comma"] = lambda n: f"{n:,}" if isinstance(n, int) else str(n)
        self._env.filters["svg_escape"] = lambda s: (
            str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )
        self._env.filters["hex_color"] = lambda v, lo, hi: self._hex_color(v, lo, hi)

        self._templates: dict[str, str] = {}
        self._discover_templates()
        log.info(f"TemplateEngine: {len(self._templates)} templates cargados desde {td}")

    # ── Discovery ────────────────────────────────────────────────────────

    def _discover_templates(self) -> None:
        """Auto-descubre templates .svg.j2 en el directorio. Excluye partials (_*)."""
        for f in sorted(_TEMPLATE_DIR.glob("*.svg.j2")):
            if f.name.startswith("_"):  # skip theme partials
                continue
            name = f.stem.replace(".svg", "")
            self._templates[name] = f.name
        if not self._templates:
            log.warning("TemplateEngine: no se encontraron templates .svg.j2")

    # ── Validation ───────────────────────────────────────────────────────

    def _validate(self, template_name: str, data: dict) -> list[str]:
        """Valida datos contra schema mínimo. Retorna lista de errores."""
        errors: list[str] = []
        schema = _SCHEMAS.get(template_name)
        if not schema:
            errors.append(f"Template desconocido: {template_name}")
            return errors

        for field in schema.get("required", []):
            if field not in data or data[field] is None:
                errors.append(f"Campo requerido faltante: '{field}'")

        return errors

    # ── Compute helpers ──────────────────────────────────────────────────

    @staticmethod
    def _num(val) -> float:
        """Convierte '2,847' o '12.4k' o 2847 a float para cálculos."""
        if isinstance(val, (int, float)):
            return float(val)
        s = str(val).replace(",", "").strip()
        mult = 1.0
        if s.lower().endswith("k"):
            s = s[:-1]
            mult = 1000.0
        elif s.lower().endswith("m"):
            s = s[:-1]
            mult = 1_000_000.0
        try:
            return float(s) * mult
        except ValueError:
            return 0.0

    @staticmethod
    def _hex_color(intensity: float, lo: int = 0, hi: int = 100) -> str:
        """Interpolate heatmap color from intensity to hex (Youkai palette).
        Cool (poco) → Hot (mucho): grey → cyan → yellow → red."""
        if hi <= lo:
            hi = lo + 1
        pct = max(0.0, min(1.0, (intensity - lo) / (hi - lo)))
        # Map to 5 levels: cool (azul/gris) → hot (rojo carmesí)
        level = int(pct * 4.99)
        # Youkai gradient: dark grey → cyan → green → yellow → red
        colors = ["#2A2A35", "#06FFA5", "#FFD60A", "#FF8C42", "#E63946"]
        return colors[min(level, 4)]

    def _compute_context(self, template_name: str, data: dict) -> dict:
        """
        Pre-computa variables de layout que los templates necesitan.
        Los cálculos pesados van AQUÍ, no en Jinja2.
        """
        ctx: dict[str, Any] = dict(data)
        ctx.setdefault("watermark", "YOUKAI")

        if template_name == "tierlist":
            tiers = data.get("tiers", [])
            n_tiers = len(tiers)
            ctx["height"] = 96 + (n_tiers * 84) + 28
            for i, tier in enumerate(tiers):
                tier["_y"] = 96 + (i * 84)
                entries = tier.get("entries", tier.get("items", []))
                for j, item in enumerate(entries):
                    if isinstance(item, dict):
                        item["_x"] = 112 + (j * 76)
                    else:
                        entries[j] = {"name": item, "_x": 112 + (j * 76)}
                tier["entries"] = entries

        elif template_name == "leaderboard":
            rows = data.get("rows", [])
            n_rows = len(rows)
            ctx["height"] = 130 + (n_rows * 60) + 24
            max_val = max((self._num(r.get("value", 0)) for r in rows), default=1)
            for i, row in enumerate(rows):
                row["_y"] = 124 + (i * 60)
                rv = self._num(row.get("value", 0))
                row["_bar_px"] = int((rv / max_val) * 200) if max_val > 0 else 0
                row["_bar_px_240"] = int((rv / max_val) * 240) if max_val > 0 else 0
                row["_bar_x"] = 440 + row["_bar_px"]
                row["_rank_badge"] = {1: "🥇", 2: "🥈", 3: "🥉"}.get(row.get("rank", 0), "")
            ctx.setdefault("period", "Histórico total")

        elif template_name == "bar_chart":
            bars = data.get("bars", [])
            n_bars = len(bars) or 1
            max_val = data.get("max_value") or max(
                (self._num(b.get("value", 0)) for b in bars), default=1
            )
            ctx["max_value"] = max_val
            spacing = 680 / n_bars
            bar_width = spacing * 0.65
            for i, bar in enumerate(bars):
                bar["_x"] = 60 + (spacing * 0.175) + (i * spacing)
                bar["_width"] = bar_width
                bv = self._num(bar.get("value", 0))
                bar["_height"] = (bv / max_val) * 310 if max_val > 0 else 0
                bar["_y"] = 400 - bar["_height"]
                bar["_center_x"] = bar["_x"] + bar_width / 2
            ctx.setdefault("y_labels", ["0", "25%", "50%", "75%", "100%"])

        elif template_name == "profile_card":
            ctx.setdefault("initials", data.get("name", "??")[:2].upper())
            ctx.setdefault("badge", "")
            ctx.setdefault("tag_role", "")
            ctx.setdefault("stats", [])
            xp_cur = data.get("xp_current", 0)
            xp_tot = data.get("xp_total", 100)
            ctx["_xp_px"] = int((xp_cur / xp_tot) * 370) if xp_tot > 0 else 0
            ctx["_xp_x"] = 135 + ctx["_xp_px"]

        elif template_name == "banner":
            ctx.setdefault("icon", "📢")
            ctx.setdefault("description", "")
            ctx.setdefault("details", "")
            ctx.setdefault("badge", "ANUNCIO")

        elif template_name == "donut_chart":
            segments = data.get("segments", [])
            total = sum(self._num(s.get("value", 0)) for s in segments)
            ctx["total"] = total
            cx, cy, r = 400, 280, 120
            start_angle = -90  # Start from top
            for seg in segments:
                val = self._num(seg.get("value", 0))
                pct = (val / total * 100) if total > 0 else 0
                sweep = (val / total) * 360 if total > 0 else 0
                end_angle = start_angle + sweep
                s_rad = math.radians(start_angle)
                e_rad = math.radians(end_angle)
                large_arc = 1 if sweep > 180 else 0
                x1 = cx + r * math.cos(s_rad)
                y1 = cy + r * math.sin(s_rad)
                x2 = cx + r * math.cos(e_rad)
                y2 = cy + r * math.sin(e_rad)
                if sweep >= 359.9:
                    e2 = math.radians(end_angle - 0.01)
                    x2a = cx + r * math.cos(e2)
                    y2a = cy + r * math.sin(e2)
                    seg["_path"] = (
                        f"M{cx},{cy} L{x1:.1f},{y1:.1f} "
                        f"A{r},{r} 0 1,1 {x2a:.1f},{y2a:.1f} Z"
                    )
                else:
                    seg["_path"] = (
                        f"M{cx},{cy} L{x1:.1f},{y1:.1f} "
                        f"A{r},{r} 0 {large_arc},1 {x2:.1f},{y2:.1f} Z"
                    )
                mid_angle = (start_angle + end_angle) / 2
                mid_rad = math.radians(mid_angle)
                label_r = r + 35
                seg["_label_x"] = cx + label_r * math.cos(mid_rad)
                seg["_label_y"] = cy + label_r * math.sin(mid_rad)
                seg["_pct"] = f"{pct:.0f}%"
                start_angle = end_angle
            ctx.setdefault("center_text", str(total))
            ctx.setdefault("center_label", "TOTAL")
            ctx["height"] = 560

        elif template_name == "stat_grid":
            stats = data.get("stats", [])
            n_stats = len(stats) or 1
            cols = min(n_stats, 4)
            rows_needed = (n_stats + cols - 1) // cols
            ctx["height"] = 80 + (rows_needed * 110) + 20
            cell_w = 740 // cols
            for i, stat in enumerate(stats):
                col = i % cols
                row = i // cols
                stat["_x"] = 30 + (col * cell_w)
                stat["_y"] = 90 + (row * 110)
                stat["_center_x"] = stat["_x"] + cell_w // 2
                stat.setdefault("trend", None)

        elif template_name == "comparison":
            left_raw = data.get("left", {}).get("stats", {})
            right_raw = data.get("right", {}).get("stats", {})
            if isinstance(left_raw, list):
                left_stats = {s.get("label", ""): s.get("value", 0) for s in left_raw}
                right_stats = {s.get("label", ""): s.get("value", 0) for s in right_raw}
            else:
                left_stats = left_raw
                right_stats = right_raw
            stat_labels = list(left_stats.keys())
            n_stats = len(stat_labels)
            ctx["height"] = 120 + (n_stats * 55) + 20
            ctx["stat_labels"] = stat_labels
            max_val = 100
            for i, label in enumerate(stat_labels):
                lv = self._num(left_stats.get(label, 0))
                rv = self._num(right_stats.get(label, 0))
                stat_labels[i] = {
                    "label": label if isinstance(label, str) else str(label),
                    "left_value": lv,
                    "right_value": rv,
                    "_y": 130 + (i * 55),
                    "_left_px": int((lv / max_val) * 250),
                    "_right_px": int((rv / max_val) * 250),
                }

        elif template_name == "radar_chart":
            axes = data.get("axes", [])
            n_axes = len(axes)
            # Ensure exactly 6 axes for hexagon
            cx, cy = 300, 225
            base_r = 140
            # Calculate vertices for each axis at 60° intervals
            for i, axis in enumerate(axes[:6]):
                # Starting at top (-90°), going clockwise
                angle_deg = -90 + (i * 60)
                angle_rad = math.radians(angle_deg)
                # Base (maximum) position
                axis["_bx"] = cx + base_r * math.cos(angle_rad)
                axis["_by"] = cy + base_r * math.sin(angle_rad)
                # Scaled value position
                val = self._num(axis.get("value", 0))
                mx = self._num(axis.get("max", 100)) or 1
                scale = val / mx
                vr = base_r * scale
                axis["_vx"] = cx + vr * math.cos(angle_rad)
                axis["_vy"] = cy + vr * math.sin(angle_rad)
                # Label position (outside the hexagon)
                label_r = base_r + 35
                axis["_lx"] = cx + label_r * math.cos(angle_rad)
                axis["_ly"] = cy + label_r * math.sin(angle_rad)

        elif template_name == "timeline":
            events = data.get("events", [])
            n_events = len(events)
            # Distribute events along 700px width, starting at x=50
            available_width = 700.0
            start_x = 55.0
            spacing = available_width / max(n_events - 1, 1) if n_events > 1 else available_width / 2
            # Height calculation: events above + below
            max_above = (n_events + 1) // 2  # ceil(n/2) for even-indexed
            max_below = n_events // 2  # floor(n/2) for odd-indexed
            ctx["height"] = 160 + max(max_above, max_below) * 65 + 20
            for i, event in enumerate(events):
                if isinstance(event, dict):
                    event["_x"] = start_x + (i * spacing)
                else:
                    events[i] = {"title": str(event), "_x": start_x + (i * spacing)}

        elif template_name == "heatmap":
            data_rows = data.get("data", [])
            ctx.setdefault("day_labels", ["L", "M", "X", "J", "V", "S", "D"])
            ctx.setdefault("hour_labels", ["0h", "4h", "8h", "12h", "16h", "20h"])
            # Compute color for each cell
            for row in data_rows:
                for cell in row:
                    if isinstance(cell, dict):
                        val = self._num(cell.get("value", 0))
                    else:
                        val = self._num(cell)
                    cell_color = self._hex_color(val, 0, 100)
                    # Store color and intensity display
                    if isinstance(cell, dict):
                        cell["_color"] = cell_color
                        cell["_intensity"] = int(val)
                    else:
                        # Need to convert to dict for template access
                        pass
            # Convert simple values to dicts if needed
            processed_rows = []
            for row in data_rows:
                processed_row = []
                for cell in row:
                    if isinstance(cell, dict):
                        val = self._num(cell.get("value", 0))
                        cell["_color"] = self._hex_color(val, 0, 100)
                        cell["_intensity"] = int(val)
                    else:
                        val = self._num(cell)
                        processed_row.append({
                            "_color": self._hex_color(val, 0, 100),
                            "_intensity": int(val),
                        })
                        continue
                    processed_row.append(cell)
                processed_rows.append(processed_row)
            ctx["data"] = processed_rows

        elif template_name == "achievement_card":
            ctx.setdefault("description", None)
            ctx.setdefault("date", None)
            ctx.setdefault("progress", None)

        elif template_name == "love_graph":
            ships = data.get("ships", [])
            n_ships = len(ships)
            if n_ships == 1:
                n_ships = 2  # Minimum 2 for love graph
            # Layout based on count
            if n_ships == 2:
                av_size = 100
                ctx["width"] = 400
                ctx["height"] = 240
                s1_cx = 150
                s2_cx = 250
                cy = 105
                for i, ship in enumerate(ships[:2]):
                    r = av_size / 2
                    cx = s1_cx if i == 0 else s2_cx
                    ship["_cx"] = cx
                    ship["_cy"] = cy
                    ship["_r"] = r
                    ship["_ix"] = cx - r
                    ship["_iy"] = cy - r
                    ship["_is"] = av_size
                    ship["_ny"] = cy + r + 22
                ctx["_hearts"] = [
                    {"x": ctx["width"] / 2, "y": 58, "size": 24},
                ]
            elif n_ships == 3:
                av_size = 80
                ctx["width"] = 400
                ctx["height"] = 300
                positions = [
                    (200, 100),  # top
                    (120, 200),  # bottom-left
                    (280, 200),  # bottom-right
                ]
                for i, ship in enumerate(ships[:3]):
                    r = av_size / 2
                    cx, cy_pos = positions[i]
                    ship["_cx"] = cx
                    ship["_cy"] = cy_pos
                    ship["_r"] = r
                    ship["_ix"] = cx - r
                    ship["_iy"] = cy_pos - r
                    ship["_is"] = av_size
                    ship["_ny"] = cy_pos + r + 22
                ctx["_hearts"] = [
                    {"x": 160, "y": 150, "size": 16},
                    {"x": 240, "y": 150, "size": 16},
                    {"x": 200, "y": 200, "size": 14},
                ]
            else:  # 4+
                av_size = 70
                ctx["width"] = 420
                ctx["height"] = 320
                positions = [
                    (140, 90),   # top-left
                    (280, 90),   # top-right
                    (140, 195),  # bottom-left
                    (280, 195),  # bottom-right
                ]
                for i, ship in enumerate(ships[:4]):
                    r = av_size / 2
                    cx, cy_pos = positions[i]
                    ship["_cx"] = cx
                    ship["_cy"] = cy_pos
                    ship["_r"] = r
                    ship["_ix"] = cx - r
                    ship["_iy"] = cy_pos - r
                    ship["_is"] = av_size
                    ship["_ny"] = cy_pos + r + 22
                # Hearts: avoid names — place them in clear space between circles
                ctx["_hearts"] = [
                    {"x": 210, "y": 85, "size": 14},   # top center
                    {"x": 210, "y": 200, "size": 14},  # bottom center
                    {"x": 140, "y": 130, "size": 12},  # left (away from names)
                    {"x": 280, "y": 130, "size": 12},  # right (away from names)
                ]

        elif template_name == "graph_network":
            nodes = data.get("nodes", [])
            edges = data.get("edges", [])
            n_nodes = len(nodes)
            ctx["max_msgs"] = data.get("max_msgs") or max((n.get("msg_count", 1) for n in nodes), default=1)
            ctx["max_weight"] = data.get("max_weight") or max((e.get("weight", 1) for e in edges), default=1)
            # Auto-size: ~600x400 area for nodes
            canvas_w, canvas_h = 600, 380
            ctx["height"] = canvas_h + 80
            # Simple circular layout
            cx_center, cy_center = 360, 160 + 50
            radius = min(canvas_w, canvas_h) // 2 - 40
            for i, node in enumerate(nodes):
                angle = 2 * math.pi * i / max(n_nodes, 1) - math.pi / 2
                node["x"] = cx_center + radius * math.cos(angle)
                node["y"] = cy_center + radius * math.sin(angle)
                node["radius"] = max(18, min(36, 18 + (node.get("msg_count", 1) / ctx["max_msgs"]) * 22))
                node.setdefault("initials", (node.get("name", "??")[:2].upper()))
                node.setdefault("name", "?")
            # Map node IDs to positions for edges
            pos_map = {n.get("id", i): (n["x"], n["y"]) for i, n in enumerate(nodes)}
            for edge in edges:
                src = pos_map.get(edge.get("source"))
                tgt = pos_map.get(edge.get("target"))
                if src and tgt:
                    edge["x1"], edge["y1"] = src
                    edge["x2"], edge["y2"] = tgt
                else:
                    edge["x1"] = edge["y1"] = edge["x2"] = edge["y2"] = 0

        elif template_name == "correlation_matrix":
            users = data.get("users", [])
            n = len(users)
            cell_size = min((780 - n * 4) // (n + 1), 50)
            ctx["height"] = 110 + n * (cell_size + 4) + 30
            ctx.setdefault("subtitle", "")

        elif template_name == "investigation_timeline":
            events = data.get("events", [])
            n = len(events)
            ctx["height"] = 160 + (n * 64) + 30
            ctx.setdefault("subtitle", "")

        return ctx

    # ── Render ───────────────────────────────────────────────────────────

    def render(self, template_name: str, data: dict) -> str:
        """
        Renderiza un template SVG con datos JSON.
        Returns: SVG string.
        """
        if template_name not in self._templates:
            available = ", ".join(sorted(self._templates.keys()))
            raise ValueError(
                f"Template '{template_name}' no encontrado. Disponibles: {available}"
            )

        errors = self._validate(template_name, data)
        if errors:
            raise ValueError(f"Datos inválidos para '{template_name}': {'; '.join(errors)}")

        ctx = self._compute_context(template_name, data)
        tmpl = self._env.get_template(self._templates[template_name])
        return tmpl.render(**ctx)

    async def render_to_png(self, template_name: str, data: dict) -> bytes:
        """
        Renderiza template + convierte a PNG via cairosvg.
        Returns: PNG bytes.
        """
        import asyncio

        svg_str = self.render(template_name, data)
        svg_bytes = svg_str.encode("utf-8")

        loop = asyncio.get_running_loop()
        png_data = await loop.run_in_executor(
            None, lambda: cairosvg.svg2png(bytestring=svg_bytes, unsafe=True)
        )
        return png_data

    def list_templates(self) -> list[dict]:
        """Lista templates disponibles con sus schemas."""
        result = []
        for name in sorted(self._templates.keys()):
            schema = _SCHEMAS.get(name, {})
            result.append({
                "name": name,
                "required": schema.get("required", []),
                "optional": schema.get("optional", []),
            })
        return result

    def get_schema(self, template_name: str) -> dict | None:
        """Retorna el schema de un template específico."""
        return _SCHEMAS.get(template_name)
