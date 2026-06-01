# SKILL: ascii_art
> Instrucciones maestras para generar arte ASCII/Unicode de alta calidad en Discord.

---

## FILOSOFÍA GENERAL

El arte ASCII para Discord no es simplemente texto. Es **expresión visual** dentro de las limitaciones del chat. El objetivo es:
- Impacto inmediato al leer
- Coherencia estética con el tono del servidor
- Uso inteligente del espacio vertical y horizontal
- Render perfecto en Discord (fuente monoespaciada en bloques de código)

Siempre envuelve arte ASCII complejo en ` ``` ` para garantizar fuente monoespaciada.

---

## PALETA DE BLOQUES UNICODE ESENCIALES

### Bloques de construcción
```
█ ▓ ▒ ░   ← densidad de relleno (100% → 25%)
▀ ▄ ▌ ▐   ← medios bloques (arriba, abajo, izquierda, derecha)
▘ ▝ ▗ ▖   ← cuartos de bloque
■ □ ▪ ▫   ← cuadrados sólidos y huecos
```

### Líneas y bordes
```
─ │ ┌ ┐ └ ┘ ├ ┤ ┬ ┴ ┼   ← caja simple
━ ┃ ┏ ┓ ┗ ┛ ┣ ┫ ┳ ┻ ╋   ← caja gruesa
═ ║ ╔ ╗ ╚ ╝ ╠ ╣ ╦ ╩ ╬   ← caja doble
╭ ╮ ╯ ╰                  ← esquinas redondeadas ← PREFERIDAS para estética moderna
```

### Flechas y decoración
```
→ ← ↑ ↓ ↔ ↕ ⇒ ⇐ ⇑ ⇓ ⟶ ⟵
◆ ◇ ◈ ● ○ ◉ ◎ ✦ ✧ ★ ☆ ✿ ❀ ❁
♦ ♣ ♠ ♥ ♡ ♢
✨ 💫 ⭐ 🌟  ← emojis que complementan bien el arte
```

### Letras decorativas (para títulos)
```
Pequeñas:  ᴀ ʙ ᴄ ᴅ ᴇ ꜰ ɢ ʜ ɪ ᴊ ᴋ ʟ ᴍ ɴ ᴏ ᴘ ǫ ʀ ꜱ ᴛ ᴜ ᴠ ᴡ x ʏ ᴢ
Cursiva:   𝘢 𝘣 𝘤 𝘥 𝘦 𝘧 𝘨 𝘩 𝘪 𝘫 𝘬 𝘭 𝘮 𝘯 𝘰 𝘱 𝘲 𝘳 𝘴 𝘵 𝘶 𝘷 𝘸 𝘹 𝘺 𝘻
Bold:      𝗮 𝗯 𝗰 𝗱 𝗲 𝗳 𝗴 𝗵 𝗶 𝗷 𝗸 𝗹 𝗺 𝗻 𝗼 𝗽 𝗾 𝗿 𝘀 𝘁 𝘂 𝘃 𝘄 𝘅 𝘆 𝘇
Monoesp:   𝚊 𝚋 𝚌 𝚍 𝚎 𝚏 𝚐 𝚑 𝚒 𝚓 𝚔 𝚕 𝚖 𝚗 𝚘 𝚙 𝚚 𝚛 𝚜 𝚝 𝚞 𝚟 𝚠 𝚡 𝚢 𝚣
```

---

## PLANTILLAS DE BORDES

### Borde elegante (preferido para anuncios)
```
╭──────────────────────────────╮
│  contenido aquí              │
╰──────────────────────────────╯
```

### Borde doble (para eventos importantes)
```
╔══════════════════════════════╗
║  TÍTULO IMPORTANTE           ║
╠══════════════════════════════╣
║  contenido                   ║
╚══════════════════════════════╝
```

### Borde decorativo con esquinas
```
┌─「 Título 」──────────────────┐
│  contenido                    │
└───────────────────────────────┘
```

### Borde con ornamentos
```
◈━━━━━━━━━━━━━━━━━━━━━━━━━━━━◈
         TEXTO CENTRADO
◈━━━━━━━━━━━━━━━━━━━━━━━━━━━━◈
```

---

## LETRAS GRANDES (FIGLET-STYLE MANUAL)

Para títulos grandes usa este sistema de 5 líneas:

### Ejemplo: "OK"
```
 ██████╗ ██╗  ██╗
██╔═══██╗██║ ██╔╝
██║   ██║█████╔╝ 
██║   ██║██╔═██╗ 
╚██████╔╝██║  ██╗
 ╚═════╝ ╚═╝  ╚═╝
```

Construye cada letra con bloques █ y ╗╔╝╚║═ para mayor elegancia.

---

## PERSONAJES CUTE (KAOMOJI AVANZADOS)

### Emociones base
```
Feliz:     (◕‿◕)  (ﾉ◕ヮ◕)ﾉ  ✧(◠‿◠)✧  (´｡• ᵕ •｡`)
Tímido:    (⁄ ⁄>⁄ ▽ ⁄<⁄ ⁄)  (*/ω＼*)  (〃＾▽＾〃)
Molesto:   (╬ Ò﹏Ó)  (ノಠ益ಠ)ノ  (눈_눈)
Asustado:  (º﹃º)  ( ; ω ; )  (⊙_⊙;)
Dormido:   (－_－) zzZ  (￣ρ￣)..zzZZ
Bailando:  ♪(┌・。・)┌  ヾ(≧▽≦*)o
```

### Animales cute
```
Gato:      /ᐠ｡ꞈ｡ᐟ\  =^._.^= ∫  ฅ(ﾐ・ﻌ・ﾐ)ฅ
Conejito:  (\ /)  (•ᴗ•)  c(")_(")
Oso:       ʕ•ᴥ•ʔ  ʕっ•ᴥ•ʔっ
Perro:     (ᵔᴥᵔ)  U・ᴥ・U
Pingüino:  (─‿‿─)♡
```

### Personajes con cuerpo completo
```
Mago:
    .  *  .   *
  *   (◕‿◕)  *  .
    *  /|\ *
       / \
    ✨ Hechizo ✨

Caballero:
   ╔═══╗
   ║ ◕‿◕ ║
   ╠═══╣
   ║[█]║
   ╚═╤═╝
     │
    /|\

Ninja:
  ╱|、
(˚ˎ 。7
 |、˜〵
 じしˍ,)ノ
```

---

## BARRAS DE PROGRESO

```python
# Llena (█) y vacía (░), longitud estándar = 20 chars
[████████████████████] 100%
[████████████░░░░░░░░] 60%
[████░░░░░░░░░░░░░░░░] 20%
[░░░░░░░░░░░░░░░░░░░░] 0%

# Versión decorativa
◈ ▰▰▰▰▰▰▰▰▰▱▱▱▱▱▱ 60% ◈

# Con emoji
🔥 [████████░░░░] 67%
⭐ [████████████] 100%
💤 [░░░░░░░░░░░░] 0%
```

---

## TABLAS ASCII

### Tabla simple
```
┌─────────────┬──────────┬───────────┐
│ Usuario     │ Mensajes │ Rango     │
├─────────────┼──────────┼───────────┤
│ MikoNezu    │ 1,234    │ 🥇 Top 1  │
│ StarLight   │   987    │ 🥈 Top 2  │
│ NightOwl    │   654    │ 🥉 Top 3  │
└─────────────┴──────────┴───────────┘
```

### Tarjeta de usuario
```
╭────────────────────────────────╮
│  👤  MikoNezu#1234             │
│ ─────────────────────────────  │
│  📅 Unido:  15 Jan 2023        │
│  💬 Msgs:   1,234              │
│  🏅 Rango:  Veterano           │
│  ⚠️  Warns:  0                  │
╰────────────────────────────────╯
```

---

## SEPARADORES Y DIVISORES

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬
· · · · · · · · · · · · · · · · · · · ·
∙∘○◉○∘∙∙∘○◉○∘∙∙∘○◉○∘∙∙∘○◉○∘∙∙∘○◉○∘∙
✦ ✧ ✦ ✧ ✦ ✧ ✦ ✧ ✦ ✧ ✦ ✧ ✦ ✧ ✦ ✧ ✦ ✧
〜〜〜〜〜〜〜〜〜〜〜〜〜〜〜〜〜〜〜〜
```

---

## REGLAS DE ORO

1. **Menos es más** — el espacio en blanco también es arte.
2. **Consistencia** — usa el mismo estilo de borde en todo el mensaje.
3. **Ancho máximo** — 45 caracteres en móvil, 60 en desktop. Preferir ≤45.
4. **Siempre en bloque de código** — ` ```\n...\n``` ` para render correcto.
5. **Prueba mental** — imagina el render en móvil antes de confirmar.
6. **Emojis como acentos** — no como relleno. Máximo 1 emoji por línea en arte ASCII.
7. **Simetría** — centra los elementos visualmente cuando el contenido lo permite.

---

## FLUJO DE TRABAJO

1. Determina el **propósito**: ¿anuncio, perfil, decoración, celebración?
2. Elige el **estilo**: cute, serio, épico, minimalista.
3. Selecciona la **plantilla de borde** adecuada.
4. Construye el **contenido interno** con tablas o kaomoji si aplica.
5. Añade **separadores** internos si hay múltiples secciones.
6. **Revisa el ancho** de cada línea (≤45 chars idealmente).
7. Envuelve en ` ``` ` y envía con `send_message` o `send_embed` según el caso.
