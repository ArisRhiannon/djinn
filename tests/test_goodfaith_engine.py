"""Suite masiva del motor automod v3.

Énfasis ABSOLUTO en 0 falsos positivos: la mayor parte de los tests verifican
que comportamiento LEGÍTIMO real de Discord (info-dumping neurodivergente,
terminally-online, emote/gif spam, pile-ons de acuerdo, copypasta, énfasis)
NUNCA recibe acción punitiva ni de cuarentena.
"""

from __future__ import annotations

import pytest

from goodfaith import Engine, Message as MessageContext, Account as AccountContext, Action
from goodfaith import text as sh
from goodfaith import behavior, reputation, config
from goodfaith.policy import Policy


# ── Builders ─────────────────────────────────────────────────────────────────

def regular_acc(uid=1, **kw):
    # Tier "regular" real: NO trusted (server<7d ó msgs<20 por encima de regular),
    # pero cuenta no-nueva. Para los tests 0-FP el tier da igual (0 llaves → allow).
    base = dict(account_age_days=120.0, server_age_days=3.0, msg_count=40, active_days=10)
    base.update(kw)
    return AccountContext(user_id=uid, **base)


def new_acc(uid=1, **kw):
    base = dict(account_age_days=0.05, server_age_days=0.0, msg_count=0, has_avatar=False)
    base.update(kw)
    return AccountContext(user_id=uid, **base)


def trusted_acc(uid=1, **kw):
    base = dict(account_age_days=900.0, server_age_days=400.0, msg_count=9000, active_days=15)
    base.update(kw)
    return AccountContext(user_id=uid, **base)


def m(author, content="", t=1.0, gid=1, cid=1, mid=None, **kw):
    return MessageContext(
        guild_id=gid, channel_id=cid, message_id=mid if mid is not None else author.user_id,
        author=author, content=content, created_at=t, **kw
    )


NON_PUNITIVE = {Action.ALLOW, Action.OBSERVE}
def assert_never_punished(decision, ctx_desc=""):
    assert decision.action in NON_PUNITIVE, (
        f"FALSO POSITIVO: {ctx_desc} → {decision.action.name} "
        f"(keys={[k.name for k in decision.keys]}, allow={decision.allowlisted})"
    )
    assert not decision.punished, f"punished on legit: {ctx_desc}"


# ═══════════════════════════════════════════════════════════════════════════
# 1. COMPORTAMIENTO LEGÍTIMO — NUNCA debe castigarse (0-FP)  [el bloque clave]
# ═══════════════════════════════════════════════════════════════════════════

LEGIT_SINGLE_MESSAGES = [
    # L4/L5 énfasis y reacciones
    "no no no no no", "WWWWWW", "LETS GOOOOO", "aaaaaaaa", "yoooooo", "PugO",
    "omg omg omg", "wait what", "SHEEEESH", "noooo way", "bruh", "lmaooooo",
    # L6 agreement
    "same", "this", "real", "fr", "frfr", "W", "L", "based", "true", "facts",
    "+1", "agreed", "mood", "felt", "valid", "fax", "deadass", "ong",
    # L8 caps cortos
    "OMG YES", "WHAT NO WAY", "STOP IT",
    # L9 markdown/subtext/spoilers/codeblocks
    "-# this is subtext", "||spoiler content here||", "```py\nprint(1)\n```",
    # one-thought / texting
    "hbu", "wyd", "lol", "ok", "yeah", "nah", "idk", "tbh", "ngl", "imo",
    # emojis / emotes only
    "😂😂😂", "🔥🔥🔥🔥", "<:kekw:123456789>", "<a:catjam:987654321>", "👍",
    # normal short chatter
    "what time is the stream", "anyone here?", "gm everyone", "good night chat",
]


@pytest.mark.parametrize("content", LEGIT_SINGLE_MESSAGES)
def test_legit_single_message_regular_never_punished(content):
    eng = Engine()
    d = eng.evaluate(m(regular_acc(), content))
    assert_never_punished(d, f"regular: {content!r}")


@pytest.mark.parametrize("content", LEGIT_SINGLE_MESSAGES)
def test_legit_single_message_new_account_never_punished(content):
    # Incluso una CUENTA NUEVA posteando chatter legítimo → nunca castigo.
    eng = Engine()
    d = eng.evaluate(m(new_acc(), content))
    assert_never_punished(d, f"new acc: {content!r}")


def test_infodump_rapid_monologue_never_punished():
    """L1/L2: monólogo info-dump (autista/TDAH): 30 mensajes rápidos seguidos."""
    eng = Engine()
    acc = regular_acc(uid=42)
    worst = Action.ALLOW
    facts = [
        "did you know that octopuses have three hearts",
        "and two of them stop beating when they swim",
        "which is why they prefer crawling honestly",
        "ALSO their blood is blue because of copper",
        "hemocyanin instead of hemoglobin its so cool",
    ] * 6
    for i, f in enumerate(facts):
        d = eng.evaluate(m(acc, f, t=i * 0.4))
        worst = max(worst, d.action)
    assert worst in NON_PUNITIVE, f"info-dump castigado: {worst.name}"


def test_single_user_rapid_fire_short_messages_never_punished():
    """L1: one-thought-per-message a alta velocidad (texting style)."""
    eng = Engine()
    acc = regular_acc(uid=7)
    msgs = ["wait", "no", "actually", "hold on", "lol", "nvm", "yeah", "ok",
            "true", "fr", "same", "lmao", "based", "W", "real", "this"]
    worst = max(eng.evaluate(m(acc, c, t=i * 0.2)).action for i, c in enumerate(msgs))
    assert worst in NON_PUNITIVE


def test_media_only_burst_never_punished():
    """L3: ráfaga de gifs/stickers sin texto."""
    eng = Engine()
    acc = regular_acc(uid=3)
    worst = Action.ALLOW
    for i in range(12):
        d = eng.evaluate(m(acc, "", t=i * 0.3, has_attachments=True))
        worst = max(worst, d.action)
    for i in range(12):
        d = eng.evaluate(m(acc, "", t=10 + i * 0.3, sticker_count=1))
        worst = max(worst, d.action)
    assert worst in NON_PUNITIVE


def test_emote_wall_never_punished():
    """L4: emote walls (terminally online) repetidos."""
    eng = Engine()
    acc = regular_acc(uid=5)
    worst = max(
        eng.evaluate(m(acc, "<:pog:1> <:pog:1> <:pog:1>", t=i * 0.2)).action
        for i in range(15)
    )
    assert worst in NON_PUNITIVE


def test_copypasta_from_trusted_never_punished():
    """L7: copypasta larga de un usuario establecido."""
    eng = Engine()
    pasta = ("What the hell did you just say about me you little. " * 20)
    d = eng.evaluate(m(trusted_acc(), pasta))
    assert_never_punished(d, "copypasta trusted")


# ═══════════════════════════════════════════════════════════════════════════
# 2. PILE-ON DE ACUERDO CROSS-USER — la trampa #1 de FP
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("word", ["W", "same", "this", "real", "fr", "+1", "based", "true", "L"])
def test_agreement_pileon_many_distinct_users_never_coordinated(word):
    """Muchos usuarios DISTINTOS (incluso nuevos) posteando la misma palabra
    corta de acuerdo NO debe contar como coordinación."""
    eng = Engine()
    actions = []
    for u in range(12):
        d = eng.evaluate(m(new_acc(uid=u), word, t=1.0))
        actions.append(d.action)
    assert all(a in NON_PUNITIVE for a in actions), f"pile-on '{word}' castigado"
    # Y específicamente: ninguna señal de coordinación se activó.
    last = eng.evaluate(m(new_acc(uid=99), word, t=1.0))
    assert not any(k.name == "coordinated_neardup" for k in last.keys)


def test_mixed_agreement_pileon_never_coordinated():
    eng = Engine()
    words = ["W", "same", "real", "fr", "this", "based", "true", "+1", "felt", "mood"]
    worst = max(eng.evaluate(m(new_acc(uid=i), w, t=1.0)).action for i, w in enumerate(words))
    assert worst in NON_PUNITIVE


# ═══════════════════════════════════════════════════════════════════════════
# 3. SIMHASH — propiedades
# ═══════════════════════════════════════════════════════════════════════════

def test_simhash_empty_is_zero():
    assert sh.simhash("") == 0
    assert sh.simhash("   ") == 0
    assert sh.simhash("😂🔥") == 0  # sin tokens \w


def test_simhash_identical_zero_distance():
    a = sh.simhash("join our free nitro giveaway server now")
    b = sh.simhash("join our free nitro giveaway server now")
    assert sh.hamming(a, b) == 0


def test_simhash_near_for_minor_edits():
    a = sh.simhash("join our free nitro giveaway server right now please")
    b = sh.simhash("join our free nitro giveaway server right now please!!!")
    assert sh.near(a, b, config.SIMHASH_MAX_HAMMING)


def test_simhash_far_for_different_text():
    a = sh.simhash("the weather today is lovely and sunny outside")
    b = sh.simhash("quantum chromodynamics describes the strong interaction")
    assert not sh.near(a, b, config.SIMHASH_MAX_HAMMING)


def test_simhash_obfuscation_normalized():
    # zero-width + homoglifo-ish + mayúsculas → mismo fingerprint
    a = sh.simhash("free nitro giveaway")
    b = sh.simhash("FREE\u200b NITRO\u200b GIVEAWAY")
    assert sh.hamming(a, b) <= config.SIMHASH_MAX_HAMMING


def test_hamming_is_symmetric_and_bounded():
    a, b = sh.simhash("alpha beta gamma delta"), sh.simhash("zeta eta theta iota")
    assert sh.hamming(a, b) == sh.hamming(b, a)
    assert 0 <= sh.hamming(a, b) <= 64


# ═══════════════════════════════════════════════════════════════════════════
# 4. REPUTACIÓN
# ═══════════════════════════════════════════════════════════════════════════

def test_reputation_tiers():
    policy = Policy()
    assert reputation.tier(trusted_acc(), policy) == reputation.TRUSTED
    assert reputation.tier(regular_acc(), policy) in (reputation.REGULAR, reputation.ESTABLISHED)
    assert reputation.tier(new_acc(), policy) == reputation.NEWCOMER


def test_established_by_volume_veteran_low_server_age():
    """Veterano con muchos mensajes pero antigüedad-en-server desconocida (proxy
    bajo) → ESTABLISHED por volumen (caso real del backtest: anuncios de mods)."""
    policy = Policy()
    acc = AccountContext(user_id=1, account_age_days=470.0, server_age_days=2.0, msg_count=504, active_days=10)
    assert reputation.tier(acc, policy) == reputation.ESTABLISHED
    assert reputation.is_trusted(acc, policy)


def test_established_by_volume_not_punitive_on_one_key():
    eng = Engine()
    veteran = AccountContext(user_id=1, account_age_days=470.0, server_age_days=2.0, msg_count=600, active_days=10)
    d = eng.evaluate(m(veteran, "everyone come to my event https://discord.gg/x",
                       external_invite=True, invite_urls=("discord.gg/x",)))
    assert not d.punished and d.action <= Action.SOFT


def test_patient_spammer_new_account_not_established_by_volume():
    """Cuenta NUEVA con 500 mensajes NO obtiene established por volumen
    (bloquea al spammer paciente que abre cuenta y postea en ráfaga)."""
    policy = Policy()
    acc = AccountContext(user_id=1, account_age_days=0.1, server_age_days=0.1, msg_count=500)
    assert reputation.tier(acc, policy) == reputation.NEWCOMER
    assert not reputation.is_trusted(acc, policy)


def test_trusted_never_punitive_even_with_two_keys():
    """Un trusted con invite externo + (forzamos) near-dup → nunca punitivo."""
    eng = Engine()
    # Primero generamos contexto near-dup con otros usuarios.
    for u in range(4):
        eng.evaluate(m(new_acc(uid=100 + u),
                       "everyone come join this brand new giveaway server now", t=1.0))
    d = eng.evaluate(m(trusted_acc(uid=1),
                       "everyone come join this brand new giveaway server now", t=1.0,
                       external_invite=True, invite_urls=("discord.gg/z",)))
    assert not d.punished
    assert d.action == Action.HOLD


def test_staff_immune_always_allow():
    eng = Engine()
    d = eng.evaluate(m(AccountContext(1, is_staff=True),
                       "@everyone free nitro discord.gg/scam", t=1.0,
                       external_invite=True, mentions_everyone=True,
                       unsafe_links=("http://x",), invite_urls=("discord.gg/scam",)))
    assert d.action == Action.ALLOW


# ═══════════════════════════════════════════════════════════════════════════
# 5. RAIDS / SPAM REAL — deben detectarse (FN bajo, pero sin romper 0-FP)
# ═══════════════════════════════════════════════════════════════════════════

def test_coordinated_substantial_raid_with_invites_punitive():
    """4 cuentas nuevas, texto sustancial casi idéntico + invite externo → punitivo
    cuando se acumulan 2 llaves (coordinated + external_invite)."""
    eng = Engine()
    actions = []
    for u in range(4):
        d = eng.evaluate(m(new_acc(uid=u),
            "join our amazing free nitro giveaway server right now everyone", t=1.0,
            external_invite=True, invite_urls=("discord.gg/x",)))
        actions.append(d.action)
    assert Action.PUNITIVE in actions, f"raid no detectado: {[a.name for a in actions]}"
    assert all(d.reversible for d in [eng.evaluate(m(new_acc(uid=50),
        "join our amazing free nitro giveaway server right now everyone", t=1.0,
        external_invite=True, invite_urls=("discord.gg/x",)))])


def test_benign_identical_raid_goes_to_review_not_punitive():
    """Raid de texto idéntico pero BENIGNO (sin links/invites) → HOLD/QUARANTINE
    (revisión humana), NUNCA timeout automático. Esto preserva 0-FP ante el
    caso raro de un pile-on de texto largo legítimo."""
    eng = Engine()
    actions = []
    for u in range(5):
        d = eng.evaluate(m(new_acc(uid=u),
            "hello everyone i am very happy to be here today friends", t=1.0))
        actions.append(d.action)
    assert Action.PUNITIVE not in actions
    # Al menos el último (con 3+ usuarios previos) dispara coordinación → HOLD/QUARANTINE
    assert any(a in (Action.HOLD, Action.QUARANTINE) for a in actions)


def test_new_account_single_external_invite_quarantine_not_punitive():
    """Cuenta nueva con UN invite externo → cuarentena reversible (1 llave),
    nunca timeout."""
    eng = Engine()
    d = eng.evaluate(m(new_acc(), "check this out discord.gg/cool", external_invite=True,
                       invite_urls=("discord.gg/cool",)))
    assert d.action == Action.QUARANTINE
    assert d.reversible and not d.punished


def test_mass_mention_plus_link_new_account_is_key():
    eng = Engine()
    d = eng.evaluate(m(new_acc(), "@everyone free stuff http://scam.tld", mentions_everyone=True,
                       unsafe_links=("http://scam.tld",)))
    # mass_mention_raid es 1 llave → al menos cuarentena, no punitivo solo.
    assert d.action in (Action.QUARANTINE, Action.HOLD)
    assert not d.punished


def test_mass_mention_link_invite_two_keys_punitive():
    eng = Engine()
    d = eng.evaluate(m(new_acc(), "@everyone free nitro discord.gg/scam http://scam.tld",
                       mentions_everyone=True, external_invite=True,
                       unsafe_links=("http://scam.tld",), invite_urls=("discord.gg/scam",)))
    assert d.action == Action.PUNITIVE  # external_invite + mass_mention_raid = 2 llaves


# ═══════════════════════════════════════════════════════════════════════════
# 6. BANCO CONOCIDO-MALO
# ═══════════════════════════════════════════════════════════════════════════

def test_known_bad_match_is_key():
    eng = Engine()
    eng.add_known_bad(1, "steam gift 50 dollars click here to claim your free code")
    d = eng.evaluate(m(new_acc(), "steam gift 50 dollars click here to claim your free code"))
    assert any(k.name == "known_bad_match" for k in d.keys)
    assert d.action in (Action.QUARANTINE, Action.HOLD)  # 1 llave → revisión


def test_known_bad_plus_invite_punitive():
    eng = Engine()
    # Realista: el mod banca el mensaje ofensor tal cual lo vio (con su invite).
    bad = "free steam gift click here to claim your code now discord.gg/x"
    eng.add_known_bad(1, bad)
    d = eng.evaluate(m(new_acc(), bad, external_invite=True, invite_urls=("discord.gg/x",)))
    assert d.action == Action.PUNITIVE  # known_bad_match + external_invite = 2 llaves


def test_known_bad_does_not_match_unrelated():
    eng = Engine()
    eng.add_known_bad(1, "free steam gift click here to claim your code")
    d = eng.evaluate(m(regular_acc(), "i love playing games on steam with friends every day"))
    assert not any(k.name == "known_bad_match" for k in d.keys)
    assert_never_punished(d, "unrelated vs bank")


def test_known_bad_trusted_user_not_punitive():
    eng = Engine()
    eng.add_known_bad(1, "free steam gift click here to claim your code now please")
    d = eng.evaluate(m(trusted_acc(), "free steam gift click here to claim your code now please"))
    assert not d.punished  # trusted → a lo sumo SOFT


# ═══════════════════════════════════════════════════════════════════════════
# 7. REGLA DE 2 LLAVES / DEFER-BAND
# ═══════════════════════════════════════════════════════════════════════════

def test_one_key_never_punitive_new():
    eng = Engine()
    d = eng.evaluate(m(new_acc(), "join discord.gg/x", external_invite=True,
                       invite_urls=("discord.gg/x",)))
    assert not d.punished


def test_one_key_never_punitive_regular():
    eng = Engine()
    d = eng.evaluate(m(regular_acc(), "join discord.gg/x", external_invite=True,
                       invite_urls=("discord.gg/x",)))
    assert d.action == Action.HOLD and not d.punished


def test_unsafe_link_alone_is_not_a_key():
    """Un link genérico (no allowlist) JAMÁS castiga — usuarios reales postean links."""
    eng = Engine()
    for acc in (regular_acc(), new_acc()):
        d = eng.evaluate(m(acc, "look at this cool site http://random-blog.example",
                           unsafe_links=("http://random-blog.example",)))
        assert_never_punished(d, "generic link")


def test_zero_keys_allow_or_observe():
    eng = Engine()
    d = eng.evaluate(m(regular_acc(), "hello world this is a normal message"))
    assert d.action in NON_PUNITIVE


# ═══════════════════════════════════════════════════════════════════════════
# 8. EDGE CASES
# ═══════════════════════════════════════════════════════════════════════════

def test_empty_message_allow():
    eng = Engine()
    assert eng.evaluate(m(new_acc(), "")).action == Action.ALLOW


def test_whitespace_only_allow():
    eng = Engine()
    assert eng.evaluate(m(new_acc(), "    \n\t  ")).action == Action.ALLOW


def test_very_long_message_single_user_not_punished():
    eng = Engine()
    d = eng.evaluate(m(regular_acc(), "lore " * 2000))
    assert_never_punished(d, "wall of text single user")


def test_unicode_and_zero_width_does_not_crash():
    eng = Engine()
    d = eng.evaluate(m(new_acc(), "f\u200br\u200be\u200be 𝓷𝓲𝓽𝓻𝓸 ✨🎉"))
    assert d.action in NON_PUNITIVE or not d.punished


def test_same_user_repeating_substantial_is_not_cross_user_coordination():
    """UN usuario repitiendo el mismo texto sustancial NO es coordinación
    cross-user (near-dup excluye al propio autor)."""
    eng = Engine()
    acc = regular_acc(uid=77)
    actions = [eng.evaluate(m(acc, "this is the same long sentence repeated again", t=i)).action
               for i in range(6)]
    assert all(a in NON_PUNITIVE for a in actions)


def test_coordination_window_expires():
    """Mensajes idénticos pero FUERA de la ventana temporal no cuentan como wave."""
    eng = Engine()
    txt = "everyone join the brand new community server today please"
    for u in range(3):
        eng.evaluate(m(new_acc(uid=u), txt, t=1.0))
    # Mucho después → near-dup index podado, no coordinación.
    far = config.NEARDUP_WINDOW_SECONDS + 100.0
    d = eng.evaluate(m(new_acc(uid=50), txt, t=far))
    assert not any(k.name == "coordinated_neardup" for k in d.keys)


def test_decision_always_reversible_when_punitive():
    eng = Engine()
    d = eng.evaluate(m(new_acc(), "@everyone free nitro discord.gg/scam http://s.tld",
                       mentions_everyone=True, external_invite=True,
                       unsafe_links=("http://s.tld",), invite_urls=("discord.gg/scam",)))
    if d.punished:
        assert d.reversible


@pytest.mark.parametrize("n", [0, 1, 2, 3, 5])
def test_neardup_threshold_boundary(n):
    """Coordinación solo a partir de NEARDUP_MIN_DISTINCT_USERS usuarios distintos."""
    eng = Engine()
    txt = "join our wonderful new free giveaway community server right now"
    for u in range(n):
        eng.evaluate(m(new_acc(uid=u), txt, t=1.0))
    d = eng.evaluate(m(new_acc(uid=999), txt, t=1.0))
    coordinated = any(k.name == "coordinated_neardup" for k in d.keys)
    assert coordinated == (n >= config.NEARDUP_MIN_DISTINCT_USERS)


def test_windows_pruning_bounds_memory():
    eng = Engine()
    for i in range(5000):
        eng.evaluate(m(new_acc(uid=i % 50), f"unique message number {i} content here", t=i * 0.001))
    total = sum(len(dq) for dq in eng.windows._neardup.values())
    assert total <= config.NEARDUP_INDEX_MAX + 10


# ═══════════════════════════════════════════════════════════════════════════
# 9. BEHAVIOR HELPERS (unit)
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("c,expected", [
    ("same", True), ("W", True), ("this!!!", True), ("real real", True),
    ("fr fr fr", True), ("join my server now", False),
    ("free nitro giveaway click here", False), ("based", True),
])
def test_is_agreement_word(c, expected):
    assert behavior.is_agreement_word(c, Policy()) is expected


@pytest.mark.parametrize("c,expected", [
    ("😂😂😂", True), ("<:kekw:1>", True), ("<a:jam:2> <:pog:3>", True),
    ("lol 😂", False), ("hello", False), ("", False),
])
def test_is_emote_emoji_only(c, expected):
    assert behavior.is_emote_emoji_only(c) is expected


@pytest.mark.parametrize("c,expected", [
    ("no no no", True), ("WWWWWW", True), ("aaaaa", True),
    ("the quick brown fox jumps", False), ("hello world friend", False),
])
def test_is_emphasis_repetition(c, expected):
    assert behavior.is_emphasis_repetition(c, Policy()) is expected


def test_is_substantial_excludes_agreement_and_short():
    policy = Policy()
    assert not behavior.is_substantial("W", policy)
    assert not behavior.is_substantial("same", policy)
    assert not behavior.is_substantial("no no no", policy)
    assert not behavior.is_substantial("lol ok", policy)
    assert behavior.is_substantial("join our free giveaway server right now everyone", policy)


# ── Regresión: hallazgos del backtest sobre histórico real ───────────────────

def test_shared_gif_link_crossuser_not_coordinated():
    """Backtest real: varios usuarios compartiendo el MISMO GIF de tenor disparaban
    coordinated_neardup (cultura de reacciones). Un link/GIF compartido NO es
    contenido coordinado → no debe marcarse."""
    eng = Engine()
    gif = "https://tenor.com/view/coco-witch-hat-atelier-atelier-coco-12345"
    actions = [eng.evaluate(m(regular_acc(uid=u), gif, t=1.0)).action for u in range(6)]
    assert all(a in NON_PUNITIVE for a in actions)
    d = eng.evaluate(m(regular_acc(uid=99), gif, t=1.0))
    assert not any(k.name == "coordinated_neardup" for k in d.keys)


def test_url_only_message_not_substantial():
    policy = Policy()
    assert not behavior.is_substantial("https://tenor.com/view/some-gif-1234", policy)
    assert not behavior.is_substantial("https://discord.gg/abc", policy)
    # pero el TEXTO de un raid (sin contar el link) sí es sustancial:
    assert behavior.is_substantial("join our amazing free server everyone https://discord.gg/x", policy)


def test_text_raid_with_inline_link_still_coordinated():
    """Quitar URLs no debe cegar un raid de TEXTO idéntico que incluye un link."""
    eng = Engine()
    txt = "everyone join our brand new free giveaway community right now https://discord.gg/x"
    for u in range(3):
        eng.evaluate(m(new_acc(uid=u), txt, t=1.0, external_invite=True, invite_urls=("discord.gg/x",)))
    d = eng.evaluate(m(new_acc(uid=99), txt, t=1.0, external_invite=True, invite_urls=("discord.gg/x",)))
    assert any(k.name == "coordinated_neardup" for k in d.keys)
