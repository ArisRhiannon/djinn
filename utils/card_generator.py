"""
CardGenerator — Motor de análisis sociológico para Character Cards.
Analiza historial de mensajes y dinámica social para perfilar usuarios.

Fix v2:
  - social_map ahora rastrea user_id→user_id (no message_id→count)
  - Los mensajes incluyen username gracias al JOIN en get_all_messages_since
  - Se pasa username al prompt para análisis más preciso
"""

from __future__ import annotations
import json
import time
import asyncio
from typing import Any, Dict, List, Optional
from loguru import logger

from .google_client import GoogleAIStudioClient


class CardGenerator:
    def __init__(self, bot) -> None:
        self.bot    = bot
        from .ai_client import get_ai_client
        ai = get_ai_client()
        self.client = GoogleAIStudioClient(bot.config.google_api_key, bot.config.google_model_name, ai_client=ai)
        self.client.load()

    async def analyze_users_batch(self, users_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not users_data:
            return []

        system_prompt = (
            "You are a high-fidelity Sociological Analyst for Youkai Agent. "
            "Synthesize chat logs and social interaction data into structured 'Character Cards'. "
            "Be clinical, perceptive, and slightly superior in your analysis. "
            "Return ONLY a valid JSON array — no markdown, no preamble. One object per user:\n"
            "[\n"
            "  {\n"
            "    \"user_id\": <int>,\n"
            "    \"card\": {\n"
            "      \"profile\": { \"name\": <str>, \"archetype\": <str> },\n"
            "      \"personality\": { \"traits\": [<str>], \"habits\": [<str>], \"summary\": <str> },\n"
            "      \"social\": { \"allies\": [<str>], \"avoided\": [<str>], \"dynamics\": <str> },\n"
            "      \"stats\": { \"score\": <int 0-100>, \"aura\": <str>, \"aura_value\": <int> },\n"
            "      \"fairy_comment\": <str>\n"
            "    }\n"
            "  }\n"
            "]\n\n"
            "Rules:\n"
            "1. Max 600 words per card.\n"
            "2. If 'current_card' is provided, evolve it — synthesize old data with new.\n"
            "3. social.allies/avoided: use display names from the interaction map.\n"
            "4. aura: creative and specific (e.g. 'Void-Touched', 'Radiant Chaos', 'Glitch Deity').\n"
            "5. score: 0-100 based on influence, activity, and social coherence.\n"
            "6. fairy_comment: witty, slightly arrogant, max 2 sentences."
        )

        batch_content = "BATCH ANALYSIS:\n\n"
        for entry in users_data:
            uid      = entry["user_id"]
            username = entry.get("username", f"User_{uid}")
            msgs     = "\n".join([f"- [{m.get('username', username)}]: {m['content']}" for m in entry["messages"][:40]])
            social   = json.dumps(entry["social_map"])
            curr     = json.dumps(entry["current_card"]) if entry["current_card"] else "None"
            batch_content += (
                f"USER ID: {uid}\nDISPLAY NAME: {username}\n"
                f"MESSAGES (latest first):\n{msgs}\n"
                f"SOCIAL INTERACTION MAP (user_id → interaction_count): {social}\n"
                f"CURRENT CARD: {curr}\n---\n"
            )

        try:
            response = await self.client.generate_response(
                system_prompt=system_prompt,
                user_content=batch_content,
                history=[],
                guild=None, channel=None, db=None,
            )
            clean = response.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[-1].rsplit("```", 1)[0]
            return json.loads(clean)
        except json.JSONDecodeError as exc:
            logger.error(f"CardGenerator: JSON inválido en respuesta: {exc}")
            return []
        except Exception as exc:
            logger.error(f"CardGenerator: error procesando lote: {exc}")
            return []

    async def run_hourly_update(self) -> int:
        logger.info("CardGenerator: iniciando actualización horaria...")
        now   = int(time.time())
        since = now - 3600

        all_msgs = await self.bot.db.get_all_messages_since(since)
        if not all_msgs:
            logger.info("CardGenerator: no hay mensajes nuevos.")
            return 0

        # Agrupar mensajes por usuario
        user_buckets: Dict[int, List[Dict]] = {}
        user_names:   Dict[int, str]        = {}

        for m in all_msgs:
            uid = m["user_id"]
            if uid not in user_buckets:
                user_buckets[uid] = []
            user_buckets[uid].append(m)
            # Guardar el nombre más reciente del usuario
            if m.get("username"):
                user_names[uid] = m["username"]

        # Construir social_map: uid → {other_uid: count}
        # Necesitamos resolver reply_to_id (message_id) → user_id del autor
        # Lo hacemos buscando el mensaje respondido en nuestro batch
        msg_author_map: Dict[int, int] = {}  # message_id → user_id (aproximado del batch)
        # No tenemos IDs de mensaje en el resultado de get_all_messages_since,
        # así que usamos co-presencia en canal como proxy social
        channel_users: Dict[int, List[int]] = {}  # channel_id → [user_ids]
        for m in all_msgs:
            cid = m["channel_id"]
            uid = m["user_id"]
            if cid not in channel_users:
                channel_users[cid] = []
            if uid not in channel_users[cid]:
                channel_users[cid].append(uid)

        social_maps: Dict[int, Dict[int, int]] = {uid: {} for uid in user_buckets}
        for cid, users_in_ch in channel_users.items():
            for uid in users_in_ch:
                if uid not in social_maps:
                    continue
                for other in users_in_ch:
                    if other != uid:
                        social_maps[uid][other] = social_maps[uid].get(other, 0) + 1

        # Reemplazar user_ids con nombres en el social_map para el prompt
        def _social_with_names(smap: Dict[int, int]) -> Dict[str, int]:
            return {user_names.get(uid, str(uid)): cnt for uid, cnt in smap.items()}

        batch_data: List[Dict[str, Any]] = []
        for uid, msgs in user_buckets.items():
            current_card = await self.bot.db.get_card(uid)
            batch_data.append({
                "user_id":     uid,
                "username":    user_names.get(uid, f"User_{uid}"),
                "messages":    msgs,
                "social_map":  _social_with_names(social_maps.get(uid, {})),
                "current_card": current_card["card_json"] if current_card else None,
            })

        updated_count = 0
        for i in range(0, len(batch_data), 5):
            batch   = batch_data[i:i + 5]
            results = await self.analyze_users_batch(batch)
            for res in results:
                uid  = res.get("user_id")
                card = res.get("card")
                if uid and card:
                    await self.bot.db.upsert_card(uid, card)
                    updated_count += 1
            await asyncio.sleep(0.1)  # no bloquear el event loop

        logger.info(f"CardGenerator: {updated_count} cards actualizadas.")
        return updated_count
