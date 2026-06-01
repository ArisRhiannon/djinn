"""Youkai Financial Services™ — Motor de préstamos agiotista.

100% determinista, sin LLM. Mensajes dinámicos con variaciones
basadas en hash del user_id + timestamp para nunca repetir exactamente.
"""

from __future__ import annotations

import hashlib
import math
import time
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional

# ── Constantes ────────────────────────────────────────────────────────────────

MIN_LOAN = 600
LOAN_TIERS = [
    {"amount": 600, "installments": 4, "min_score": 0},
    {"amount": 1000, "installments": 5, "min_score": 300},
    {"amount": 1500, "installments": 6, "min_score": 500},
]
DEFAULT_SCORE = 500
SCORE_MIN, SCORE_MAX = 0, 1000
SCORE_ON_PAY = 15
SCORE_ON_MISS = -40
SCORE_BONUS_CLEAN = 30
SCORE_PENALTY_DEFAULT = -100
CONSECUTIVE_MISSES_TO_DEFAULT = 3
BLACKLIST_THRESHOLD = 2  # defaults needed to blacklist at score 0


# ── Interés ───────────────────────────────────────────────────────────────────

def calculate_interest(score: int, treasury_balance: Optional[int] = None, total_capital: Optional[int] = None) -> float:
    """Score 1000→20%, Score 0→200%. Lineal.
    Si se proveen datos de tesorería, se aplica prima por baja liquidez si
    los fondos disponibles son inferiores al capital total de la caja.
    """
    s = max(SCORE_MIN, min(SCORE_MAX, score))
    base_rate = round(2.0 - (s / 1000) * 1.8, 2)
    if treasury_balance is not None and total_capital is not None and total_capital > 0:
        liquidity = min(1.0, max(0.0, treasury_balance / total_capital))
        premium = (1.0 - liquidity) * 0.5
        return round(base_rate + premium, 2)
    return base_rate


def get_tier_name(score: int) -> str:
    if score >= 800: return "S"
    if score >= 600: return "A"
    if score >= 400: return "B"
    if score >= 200: return "C"
    return "D"


def get_tier_label(score: int) -> str:
    labels = {"S": "Excelente", "A": "Bueno", "B": "Regular", "C": "Malo", "D": "Peligro"}
    return labels[get_tier_name(score)]


def compute_loan(amount: int, score: int, treasury_balance: Optional[int] = None, total_capital: Optional[int] = None) -> dict:
    """Calcula los términos de un préstamo."""
    rate = calculate_interest(score, treasury_balance, total_capital)
    total = math.ceil(amount * (1 + rate))
    tier = next((t for t in LOAN_TIERS if t["amount"] == amount), LOAN_TIERS[0])
    n = tier["installments"]
    installment = math.ceil(total / n)
    return {
        "principal": amount,
        "rate": rate,
        "total_owed": total,
        "installments": n,
        "installment_amt": installment,
    }


def available_tiers(score: int) -> list[dict]:
    """Tiers disponibles para el score dado."""
    return [t for t in LOAN_TIERS if score >= t["min_score"]]


# ── Mensajes dinámicos (nunca se repiten exactamente) ─────────────────────────

def _pick(options: list[str], user_id: int, salt: str = "") -> str:
    """Selecciona una variación basada en hash determinista pero variable en el tiempo."""
    h = hashlib.md5(f"{user_id}:{salt}:{int(time.time()) // 60}".encode()).hexdigest()
    idx = int(h, 16) % len(options)
    return options[idx]


def _format(template: str, **kwargs) -> str:
    return template.format(**kwargs)


# ── Mensajes de oferta ────────────────────────────────────────────────────────

_OFFER_TITLES = [
    "Sin créditos. Qué predecible.",
    "Otra forma de vida sin fondos.",
    "Mira quién viene arrastrándose~",
    "Se te acabó la suerte, ¿hm?",
    "Y O U K A I · S E R V I C E S",
    "Huelo la desesperación desde aquí.",
    "Otro cliente potencial... interesante.",
]

_OFFER_BODIES = [
    "Puedo prestarte. Solo te costará... tu tranquilidad.",
    "Tengo una oferta. Puedes rechazarla. Pero no deberías.",
    "¿Quieres seguir usando mis servicios? Hay un precio. Siempre hay un precio.",
    "El crédito es un invento hermoso. Para mí, claro.",
    "Mis tasas son... competitivas. Para un depredador.",
    "Puedo ayudarte. La pregunta es si puedes pagarme después.",
]

_ACCEPT_MESSAGES = [
    "Trato hecho. El dinero ya es tuyo... por ahora.",
    "Firmado. Mañana empiezo a cobrar. Dulces sueños~",
    "Excelente decisión. O la peor de tu vida. Ya veremos.",
    "Depositado. El reloj empieza a correr.",
    "Hecho. Recuerda: yo nunca olvido una deuda.",
    "Bienvenido al club de los endeudados. Población: tú.",
]

_ALREADY_DEBT = [
    "Ya me debes **{debt}** créditos. Paga primero.",
    "¿Más dinero? Primero salda tu deuda de **{debt}**.",
    "Tienes una deuda activa de **{debt}**. No soy estúpido.",
    "Paga los **{debt}** que me debes y hablamos.",
]

_BLACKLISTED = [
    "Tu historial crediticio es tan desastroso que ni yo te presto.",
    "Estás en mi lista negra. Gana créditos como los demás mortales.",
    "Blacklisted. Tu score es un chiste. No hay trato.",
]

_MOROSO_TITLES = [
    "AVISO DE MOROSO",
    "DEUDOR IDENTIFICADO",
    "ALERTA DE IMPAGO",
    "MOROSO DETECTADO",
]

_MOROSO_SUBTITLES = [
    "Este individuo le debe dinero a Y O U K A I · S E R V I C E S",
    "Deudor registrado en el sistema.",
    "Impago confirmado. La vergüenza es el primer paso.",
    "Se le advirtió. No escuchó. Ahora todos lo saben.",
]


def msg_offer_title(user_id: int) -> str:
    return _pick(_OFFER_TITLES, user_id, "title")


def msg_offer_body(user_id: int) -> str:
    return _pick(_OFFER_BODIES, user_id, "body")


def msg_accept(user_id: int) -> str:
    return _pick(_ACCEPT_MESSAGES, user_id, "accept")


def msg_already_debt(user_id: int, debt: int) -> str:
    return _format(_pick(_ALREADY_DEBT, user_id, "debt"), debt=debt)


def msg_blacklisted(user_id: int) -> str:
    return _pick(_BLACKLISTED, user_id, "black")


def msg_moroso_title(user_id: int) -> str:
    return _pick(_MOROSO_TITLES, user_id, "moroso_t")


def msg_moroso_subtitle(user_id: int) -> str:
    return _pick(_MOROSO_SUBTITLES, user_id, "moroso_s")
