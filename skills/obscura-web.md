---
name: obscura-web
description: Navegación web con Obscura — fetching, scraping, y búsqueda de información externa.
category: web
---

# SKILL: obscura-web
> Navegación y extracción de contenido web con Obscura headless browser.

## Herramienta disponible
`web_fetch(url, selector?, wait?)` — visita una URL y devuelve el texto de la página.

## Cuándo usarla
- El usuario pide información que no está en el historial de mensajes del servidor
- Necesitas datos actualizados de la web (documentación, APIs, wikis, noticias)
- Investigar un tema que requiere fuentes externas
- Verificar hechos, definiciones, o datos que no conoces con certeza
- Buscar información sobre juegos, personajes, builds, guías (Genshin, ZZZ, etc.)
- Consultar documentación técnica, changelogs, o releases

## Cuándo NO usarla
- Para buscar mensajes del servidor → usa `search_messages` o `investigate_topic`
- Para datos de usuarios → usa `batch_user_lookup`
- Para gráficos o visualizaciones → usa `render_template`
- Para información trivial que ya conoces con certeza

## Cómo usarla

### Búsqueda básica
```
web_fetch(url="https://ejemplo.com/pagina")
```
Devuelve el texto completo de la página (hasta 8000 chars).

### Con selector CSS
Si solo necesitas una sección específica:
```
web_fetch(url="https://ejemplo.com", selector=".main-content")
```

### Con más tiempo de espera
Para páginas muy dinámicas (SPA, React, etc.):
```
web_fetch(url="https://spa-ejemplo.com", wait="8")
```

## Buenas prácticas

1. **Sé específico con las URLs.** No uses google.com como página de inicio — mejor construye URLs directas a la información.
2. **Prefiere wikis oficiales.** Para juegos: honeyhunterworld.com (ZZZ), genshin-impact.fandom.com, etc.
3. **Interpreta, no copies.** Procesa la información y responde con tus propias palabras.
4. **Cita la fuente.** Menciona de dónde sacaste la info para dar credibilidad.
5. **Límites.** 30s timeout, 8000 chars máx de respuesta. Si la página es muy grande, usa `selector`.

## Manejo de errores
- Si `web_fetch` devuelve error, intenta con una URL alternativa
- Si la página está vacía, puede ser una SPA que requiere JS — prueba con `wait` más alto
- Si el contenido es irrelevante, intenta con un `selector` más específico
- Si todo falla, admite que no pudiste obtener la info y sugiere al usuario que la busque manualmente
