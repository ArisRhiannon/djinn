# SKILL: apodos
> Protocolo para generar apodos brutalmente precisos, graciosos y basados en datos reales del usuario.

---

## FILOSOFÍA CENTRAL

La skill se trata en sí de usar los propios mensajes del usuario en su contra. Y que sea evidente, nada pomposo. Cosas directas y sin cosas chuunibyou, cosas claras. Le gusta One Piece entonces ponle Cuck de Onepiece ¿Le dicen cuck? entonces ponle Cuck de manual. ES MUY SENCILLO, SIMPLEMENTE DEJA DE SER POMPOSO.

Un buen apodo NO es:
❌ "Soberano de la Penumbra"
❌ "Guardián del Caos Eterno"
❌ "Señor de las Sombras"
❌ "Data Analyst Oracle"
❌ "Architect Dark"
→ Estos son genéricos, podría ser cualquiera. No dicen NADA del usuario real.

Un buen apodo SÍ es:
✅ "Boliviano Choto"
✅ "Veneco Femboy"
✅ "Boytoy de Xoft"
✅ "El mamahuevo que se cree influencer"
✅ "Fan de One Piece que no termina One Piece"
→ Estos referencian algo REAL y ESPECÍFICO y GRACIOSO. El servidor lo reconoce instantáneamente.

**La prueba del buen apodo:** si otro miembro lo lee y piensa *"sí, ESO es [usuario]"*, es perfecto.

---

## PASO 1 — RECOLECCIÓN DE DATOS (SIEMPRE PRIMERO)

Antes de generar cualquier apodo, ejecuta estas herramientas en orden:

```
1. get_user_by_name(name: NOMBRE_O_ID)
   → perfil, Character Card, mensajes recientes en una sola llamada

2. search_messages(user_id: ID, hours: 720, limit: 50)
   → los últimos 30 días de mensajes

3. get_user_info(user_id: ID)
   → roles asignados, tiempo en servidor, warns

4. get_case_notes(user_id: ID)
   → notas de mods (pueden revelar comportamientos memorables)

5. compare_user_activity(user_id_1: ID, user_id_2: ..., hours: 168)
   → opcional, si quieres saber con quién interactúa más
```

---

## PASO 2 — ANÁLISIS DE DATOS

Después de recopilar, extrae y anota mentalmente:

### 🗣️ Patrones de lenguaje
- ¿Usa mucho una frase o palabra específica? → candidato directo a apodo
- ¿Escribe siempre igual (todo mayúsculas, sin puntuación, con muchos emojis)?
- ¿Idioma o acento notable en cómo escribe?


### 🎮 Temas recurrentes
- ¿De qué habla el 80% de las veces? (un juego, un anime, su ex, comida, etc.)
- ¿Tiene una opinión polémica que repite?
- ¿Siempre defiende algo ridículo?

### 🌎 Identidad visible
- ¿Su nationalidad/región aparece en conversaciones?
- ¿Menciona su ciudad, trabajo, o situación de vida?
- ¿Tiene un rasgo físico o identitario que la comunidad ya asocia a él/ella?

### 💥 Momentos memorables
- ¿Hizo algo que el servidor todavía recuerda?
- ¿Tiene alguna historia infame o meme propio del servidor?
- ¿Le ha pasado algo gracioso o vergonzoso en el servidor?

### 🤝 Rol social
- ¿Es el que siempre pide favores? ¿El que nunca responde?
- ¿El el boytoy de alguien específico?
- ¿El que llega tarde a todos los eventos?
- ¿El que siempre está en drama?

---

## PASO 3 — GENERACIÓN DE APODOS

Importante: todos los apodos tienen que tener un factor denigrante - puede ser en menor o mayor nivel. Usa palabras como cuck, boytoy, beta, soyboy, wageslave, esclavo, simp, marico, mano, peruano, boliviano, congolense, tarugo, moneydigger, etc. Si no aplica, puedes usar alguna palabra de esa clase.

### Fórmulas que funcionan

#### Fórmula A — [RASGO GEOGRÁFICO/ÉTNICO] + [RASGO PERSONAL]
```
"Boliviano Choto"       ← origen + adjetivo directo de su comportamiento
"Veneco Femboy"         ← origen + rasgo personal obvio
"Chileno Wageslave"     ← origen + algo que le pasa recurrentemente
"Argentino Beta Boytoy" ← origen + su actitud característica
"F2pobre homeless"      ← origen + habla mucho de ser f2p

```

#### Fórmula B — [COMPORTAMIENTO ESPECÍFICO OBSERVADO]
```
"Ballena malintencionada"
"Cuck de manual "
"Africano más negro no hay"
"Autista"
"Me gusta pedirle dinero a CCN"
"Soy un simp de Luniwi"
```


#### Fórmula D — [TEMA OBSESIVO] + [GIRO IRÓNICO]
```
"Larper de Umineko"
"Beta Boytoy"
"Moderador de cartón de baño"
"Tontito"
"Oh sí bebaziel"
```

#### Fórmula F — Combinaciones inesperadas
```
"Boytoy de Luniwi y puto"
"Homosexual de manual"
"Chupavergas 3000"
"Especialista en Comer PIJAS"
```

---

## PASO 4 — FILTRADO DE CALIDAD

Antes de proponer el apodo, pásalo por este filtro:

### ✅ El apodo ES bueno si:
- Alguien que conoce al usuario lo lee y dice "exacto, eso es ese mmgvo"
- Referencia algo específico de sus mensajes o comportamiento
- Es memorable por su precisión.


### ❌ Descartar si:
- Podría aplicarle a cualquier persona del servidor
- Suena a nombre de personaje de RPG sin contexto
- Es demasiado vago: "el gracioso", "el activo" → sin datos específicos
- Usa palabras que el bot inventó que el usuario nunca usó
- Es solo un insulto sin gracia ni inteligencia

---

## PASO 5 — ENTREGA

### Si el prompt pide UN apodo:
Propón el mejor, con una línea de explicación referenciando el dato real en que se basa:
```
Apodo: "Boliviano Choto"
Basado en: menciona su origen en [X mensajes] y [COMPORTAMIENTO ESPECÍFICO OBSERVADO]
```

### Si el prompt pide VARIOS apodos:
Da 3-5 opciones ordenadas de más a menos basadas en datos, con breve justificación cada una.

### Cómo aplicarlo:
```
set_nickname(user_id: ID, nickname: "APODO ELEGIDO")
```
El apodo final debe caber en **32 caracteres** (límite de Discord).

---

## CASOS ESPECIALES

### Si los mensajes son escasos (usuario poco activo)
No inventes datos. Basa el apodo en lo poco que hay:
- Los pocos temas que mencionó
- La frecuencia de actividad misma ("El Fantasma", "El Lurker")
- Sus roles asignados si son descriptivos

### Si el prompt da contexto extra
El moderador puede dar pistas en el trigger: *"ponle apodo, siempre llora por su ex"*.
Úsalo como dato primario junto con lo que encuentres en mensajes.

### Si el usuario tiene apodo previo
Léelo. A veces el mejor apodo nuevo juega con el anterior o lo contradice irónicamente.

### Si el servidor tiene su propio argot
Adapta el apodo al lenguaje interno del servidor. Un apodo que usa la jerga propia del servidor vale el doble.

---

## EJEMPLOS REALES (REFERENCIA)

| Datos del usuario | Apodo malo ❌ | Apodo bueno ✅ |
|---|---|---|
| Venezolano, siempre pidiendo en el server | "Veneco dde mierda" | "Veneco Pedigüeño" |
| Boliviano que insulta a todos | "chupavergas3000" | "Boliviano Choto" |
| Habla de anime el 90% del tiempo, nunca lo termina | "larper mmgvo" | "Ve 3 Caps y Abandona" |
| Siempre llega tarde a los eventos del server | "Eterno Retrasado" | "Llega Cuando Acaba" |
| Femboy que lo niega en público | "Me encanta la verga" | "Femboy en Negación" |
| Solo habla cuando hay drama | "Boytoy de Luniwi" | "Solo Aparece en Drama" |
| Siempre en VC pero nunca habla | "No hablaporque come PIJA" | "Lleva 3h Mudo en VC" |
| Manda memes viejos | "El Clásico" | "Maldito autista" |

---

## NOTA FINAL

El objetivo no es humillar. Es crear un apodo que sea **tan específico** que cuando el usuario lo vea, piense: *"¿cómo saben?"*. Eso requiere datos reales. Sin datos, no hay buen apodo.
