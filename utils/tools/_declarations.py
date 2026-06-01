"""Tool declarations for Youkai's LLM bridge.

Extraído del monolito utils/discord_tools.py el 2026-05-16. Las definiciones
de helpers (_str, _int, _bool, _decl) y la lista grande TOOL_DECLARATIONS
viven aquí; ToolExecutor (la clase con los handlers) sigue en discord_tools.py.

Si añadís una nueva tool:
  1. Añadí su _decl(...) en TOOL_DECLARATIONS abajo.
  2. Añadí su _do_<name>() handler dentro de ToolExecutor (discord_tools.py).
  3. Si requiere permisos, agregala a TOOL_REQUIRED_PERMS en utils/security.py.
"""
from __future__ import annotations

from google.genai import types

def _str(desc: str, enum: list | None = None) -> types.Schema:
    kwargs: dict = {"type": "STRING", "description": desc}
    if enum:
        kwargs["enum"] = enum
    return types.Schema(**kwargs)

def _int(desc: str) -> types.Schema:
    return types.Schema(type="INTEGER", description=desc)

def _bool(desc: str) -> types.Schema:
    return types.Schema(type="BOOLEAN", description=desc)

def _decl(name: str, desc: str, props: dict, required: list[str]) -> types.FunctionDeclaration:
    return types.FunctionDeclaration(
        name=name,
        description=desc,
        parameters=types.Schema(type="OBJECT", properties=props, required=required),
    )


# ── Declaraciones de herramientas ─────────────────────────────────────────────

TOOL_DECLARATIONS: list[types.FunctionDeclaration] = [

    # MODERACIÓN
    _decl("ban_user",
        "Banea permanentemente a un usuario del servidor. Sácalo para siempre, bótalo. "
        "Sinónimos: banear, sacar permanente, echar para siempre, bótalo, sácalo del server.",
        {"user_id": _str("ID numérico del usuario"), "reason": _str("Razón del baneo"),
         "delete_days": _int("Días de mensajes a eliminar (0-7)")},
        ["user_id"]),

    _decl("kick_user",
        "Expulsa/kickea a un usuario (puede volver a unirse). Échalo, sácalo, bótalo. "
        "Sinónimos: kickear, expulsar, echar, sacar, bótalo, córrelo.",
        {"user_id": _str("ID numérico del usuario"), "reason": _str("Razón de la expulsión")},
        ["user_id"]),

    _decl("mute_user",
        "Silencia/mutea a un usuario con timeout temporal de Discord. Cállalo, ponle timeout. "
        "Quita temporalmente la capacidad de escribir. "
        "NO funciona con bots. Para aislamiento avanzado → seal_user. "
        "Sinónimos: silenciar, mutear, callar, cállalo, ponle mute, timeout, siléncialo.",
        {"user_id": _str("ID numérico del usuario"),
         "duration": _str("Duración del timeout", enum=["10m", "30m", "1h", "6h", "12h", "1d", "7d", "28d"]),
         "reason": _str("Razón del silencio")},
        ["user_id", "duration"]),

    _decl("unmute_user",
        "Quita el mute/timeout de un usuario. Déjalo hablar de nuevo, desmutéalo. "
        "Sinónimos: desmutear, quitar mute, quitar timeout, déjalo hablar, quítale el silencio.",
        {"user_id": _str("ID numérico del usuario"), "reason": _str("Razón")},
        ["user_id"]),

    _decl("warn_user",
        "Dale una advertencia/warn formal a un usuario, registrada en DB. "
        "A las 3 advertencias se aplica timeout de 1h. "
        "Sinónimos: advertir, dar warn, adviértele, ponle warn, dale advertencia.",
        {"user_id": _str("ID numérico del usuario"), "reason": _str("Razón de la advertencia")},
        ["user_id", "reason"]),

    _decl("get_warnings",
        "Consulta el historial de advertencias de un usuario.",
        {"user_id": _str("ID numérico del usuario")}, ["user_id"]),

    _decl("clear_warnings",
        "Elimina todas las advertencias de un usuario.",
        {"user_id": _str("ID numérico del usuario")}, ["user_id"]),

    _decl("unban_user",
        "Desbanea a un usuario, levanta el ban. Déjalo volver al server. "
        "Sinónimos: desbanear, quitar ban, levanta el ban, déjalo entrar de nuevo.",
        {"user_id": _str("ID numérico del usuario baneado"),
         "reason": _str("Razón del desbaneo (opcional)")},
        ["user_id"]),

    _decl("softban_user",
        "Banea y desbanea inmediatamente para eliminar mensajes recientes "
        "sin expulsión permanente. Requiere BAN_MEMBERS.",
        {"user_id": _str("ID numérico del usuario"),
         "delete_days": _int("Días de mensajes a eliminar (1-7, default 1)"),
         "reason": _str("Razón (opcional)")},
        ["user_id"]),

    _decl("get_infractions_summary",
        "Resumen global del servidor: cuántos bans, kicks, mutes y warns "
        "ocurrieron en las últimas N horas.",
        {"hours": _int("Ventana de tiempo en horas (default 24, máx 720)")}, []),

    _decl("mass_timeout",
        "Aplica timeout simultáneo a múltiples usuarios. Ideal para antiraid. "
        "Ignora bots. Requiere MODERATE_MEMBERS.",
        {"user_ids": _str("IDs separados por coma, ej: '111,222,333'"),
         "duration": _str("Duración: 10m, 1h, 1d, 7d (máx 28d). Default: 1h"),
         "reason": _str("Razón del timeout masivo (opcional)")},
        ["user_ids"]),

    _decl("watch_user",
        "Marca a un usuario para monitoreo activo.",
        {"user_id": _str("ID del usuario"), "reason": _str("Por qué se vigila (opcional)")},
        ["user_id"]),

    _decl("unwatch_user",
        "Quita la vigilancia de un usuario.",
        {"user_id": _str("ID del usuario")}, ["user_id"]),

    _decl("list_watched_users",
        "Lista todos los usuarios actualmente bajo vigilancia en este servidor.",
        {}, []),

    _decl("case_note",
        "Añade una nota interna sobre un usuario, visible solo para mods.",
        {"user_id": _str("ID del usuario"), "note": _str("Texto de la nota")},
        ["user_id", "note"]),

    _decl("get_case_notes",
        "Obtiene todas las notas internas de un usuario.",
        {"user_id": _str("ID del usuario")}, ["user_id"]),

    _decl("antiraid_scan",
        "Escanea el servidor para detectar posibles raiders.",
        {"hours": _str("Ventana de tiempo en horas (default 0.5 = últimos 30min)"),
         "min_messages": _int("Mínimo de mensajes para considerar sospechoso (default 5)")},
        []),

    # GESTIÓN DE CANAL
    _decl("purge_messages",
        "Borra/elimina mensajes recientes de un canal (máx 100). Limpia el chat. "
        "Sinónimos: borrar mensajes, limpiar chat, eliminar mensajes, purgar, borra todo.",
        {"count": _int("Número de mensajes a eliminar (1-100)"),
         "channel_id": _str("ID del canal (opcional)"),
         "user_id": _str("Solo borrar mensajes de este usuario (opcional)")},
        ["count"]),

    _decl("lock_channel",
        "Cierra/bloquea un canal para que los miembros no puedan escribir. "
        "Sinónimos: cerrar canal, bloquear canal, lockear, ciérralo, que nadie escriba.",
        {"channel_id": _str("ID del canal (opcional)"), "reason": _str("Razón del bloqueo")},
        []),

    _decl("unlock_channel",
        "Abre/desbloquea un canal previamente cerrado. Permite escribir de nuevo. "
        "Sinónimos: abrir canal, desbloquear, unlockear, ábrelo, déjalos escribir.",
        {"channel_id": _str("ID del canal (opcional)")}, []),

    _decl("set_slowmode",
        "Establece modo lento en un canal (0 = desactivar). Requiere MANAGE_CHANNELS.",
        {"seconds": _int("Segundos entre mensajes (0-21600)"),
         "channel_id": _str("ID del canal (opcional)")},
        ["seconds"]),

    _decl("rename_channel",
        "Renombra un canal de texto o voz. Requiere MANAGE_CHANNELS.",
        {"new_name": _str("Nuevo nombre del canal"),
         "channel_id": _str("ID del canal (opcional, usa el actual si se omite)")},
        ["new_name"]),

    _decl("set_channel_topic",
        "Establece o actualiza el tema de un canal de texto. Requiere MANAGE_CHANNELS.",
        {"topic": _str("Nuevo tema del canal (vacío para borrar)"),
         "channel_id": _str("ID del canal (opcional, usa el actual)")},
        []),

    _decl("send_message",
        "Envía un mensaje o anuncio a un canal de texto.",
        {"channel_id": _str("ID del canal destino"), "content": _str("Texto del mensaje"),
         "ping_everyone": _bool("Si hacer ping a @everyone")},
        ["channel_id", "content"]),

    _decl("cross_guild_send",
        "SYSTEM OVERRIDE — Envía un mensaje a CUALQUIER canal de CUALQUIER servidor donde Youkai esté. "
        "Solo disponible para Aris.",
        {"guild_id": _str("ID del servidor destino"),
         "channel_id": _str("ID del canal destino"),
         "content": _str("Texto del mensaje")},
        ["guild_id", "channel_id", "content"]),

    _decl("list_guilds",
        "SYSTEM OVERRIDE — Lista todos los servidores donde Youkai está conectado (nombre + ID + member count).",
        {}, []),

    _decl("find_cross_guild_channel",
        "SYSTEM OVERRIDE — Busca canales por nombre en otro servidor. Devuelve IDs.",
        {"guild_id": _str("ID del servidor"), "name": _str("Nombre parcial del canal a buscar")},
        ["guild_id", "name"]),

    _decl("add_reaction",
        "Añade una reacción emoji a un mensaje específico.",
        {"message_id": _str("ID del mensaje"), "emoji": _str("Emoji a añadir"),
         "channel_id": _str("ID del canal (opcional)")},
        ["message_id", "emoji"]),

    _decl("pin_message",
        "Fija un mensaje en el canal. Requiere MANAGE_MESSAGES.",
        {"message_id": _str("ID del mensaje a fijar"),
         "channel_id": _str("ID del canal (opcional)")},
        ["message_id"]),

    _decl("unpin_message",
        "Desfija un mensaje del canal. Requiere MANAGE_MESSAGES.",
        {"message_id": _str("ID del mensaje a desfijar"),
         "channel_id": _str("ID del canal (opcional)")},
        ["message_id"]),

    _decl("create_thread",
        "Crea un hilo de conversación a partir de un mensaje. Requiere MANAGE_THREADS.",
        {"message_id": _str("ID del mensaje base"), "thread_name": _str("Nombre del hilo"),
         "channel_id": _str("ID del canal (opcional)"),
         "auto_archive": _int("Minutos antes de archivar: 60, 1440, 4320, 10080")},
        ["message_id", "thread_name"]),

    _decl("create_channel",
        "Crea un canal de texto o voz en el servidor. Requiere MANAGE_CHANNELS.",
        {"name": _str("Nombre del canal"),
         "type": _str("Tipo de canal: 'text' o 'voice' (default 'text')"),
         "category_id": _str("ID de la categoría donde crear el canal (opcional)"),
         "topic": _str("Tema del canal de texto (opcional)"),
         "reason": _str("Razón del audit log (opcional)")},
        ["name"]),

    _decl("move_channel",
        "Mueve un canal a una categoría diferente. Requiere MANAGE_CHANNELS.",
        {"channel_id": _str("ID del canal a mover"),
         "category_id": _str("ID de la categoría destino (vacío para quitar de categoría)")},
        ["channel_id"]),

    _decl("clone_channel",
        "Duplica un canal (texto o voz) con sus permisos y configuración.",
        {"channel_id": _str("ID del canal a clonar"),
         "new_name": _str("Nombre del canal clonado (opcional)")},
        ["channel_id"]),

    _decl("get_channel_permissions",
        "Muestra los overwrites de permisos de cada rol/miembro en un canal específico.",
        {"channel_id": _str("ID del canal")}, ["channel_id"]),

    _decl("set_channel_permissions",
        "Añade o quita permisos a un rol O miembro en un canal específico. Requiere MANAGE_CHANNELS.",
        {"channel_id": _str("ID del canal"), "target_id": _str("ID del rol o del usuario/miembro"),
         "allow_perms": _str("Permisos a PERMITIR separados por coma"),
         "deny_perms": _str("Permisos a DENEGAR separados por coma"),
         "reset_perms": _str("Permisos a RESETEAR separados por coma")},
        ["channel_id", "target_id"]),

    _decl("list_categories",
        "Lista todas las categorías del servidor con sus canales hijos.",
        {}, []),

    _decl("archive_thread",
        "Archiva o desarchiva un hilo manualmente. Requiere MANAGE_THREADS.",
        {"thread_id": _str("ID del hilo"),
         "archive": _bool("True para archivar, False para desarchivar (default True)")},
        ["thread_id"]),

    # DESCUBRIMIENTO DE CANALES Y MENSAJES
    _decl("find_channel",
        "Busca canales por nombre (búsqueda parcial case-insensitive). Devuelve el channel_id, "
        "tipo, categoría y topic de cada coincidencia. "
        "Úsala cuando un usuario menciona un canal por nombre (ej: 'general', 'leaks') y necesitas "
        "su channel_id. NO adivines channel_ids — siempre usa esta tool primero.",
        {"name": _str("Nombre parcial del canal a buscar, ej: 'general', 'leaks', 'bots'")},
        ["name"]),

    _decl("get_message",
        "Obtiene el contenido completo de un mensaje específico por ID. "
        "Devuelve autor, contenido, timestamp, canal, attachments, reacciones y si fue editado.",
        {"message_id": _str("ID del mensaje a obtener"),
         "channel_id": _str("ID del canal donde está el mensaje (opcional, pero recomendado)")},
        ["message_id"]),

    # ROLES
    _decl("assign_role",
        "Dale/asigna un rol a un usuario. Ponle el rol. "
        "Sinónimos: dar rol, poner rol, asignar rol, dale el rol, ponle rol.",
        {"user_id": _str("ID del usuario"), "role_id": _str("ID del rol")},
        ["user_id", "role_id"]),

    _decl("remove_role",
        "Quita un rol a un usuario. Remueve el rol, quítaselo. "
        "Sinónimos: quitar rol, remover rol, quítale el rol, sácale el rol.",
        {"user_id": _str("ID del usuario"), "role_id": _str("ID del rol")},
        ["user_id", "role_id"]),

    _decl("create_role",
        "Crea un nuevo rol en el servidor. Requiere MANAGE_ROLES.",
        {"name": _str("Nombre del rol"),
         "color": _str("Color hexadecimal ej: #ED4245 (opcional)"),
         "mentionable": _bool("Si puede ser mencionado"),
         "hoist": _bool("Si mostrar miembros separados en la lista")},
        ["name"]),

    _decl("bulk_assign_role",
        "Asigna (o quita) un rol a múltiples usuarios a la vez. Requiere MANAGE_ROLES.",
        {"role_id": _str("ID del rol a asignar o quitar"),
         "user_ids": _str("IDs de usuarios separados por coma"),
         "action": _str("'add' para asignar, 'remove' para quitar (default 'add')")},
        ["role_id", "user_ids"]),

    _decl("get_role_members",
        "Lista todos los miembros que tienen un rol específico.",
        {"role_id": _str("ID del rol")}, ["role_id"]),

    _decl("list_roles",
        "Lista TODOS los roles del servidor con su ID, color, posición, conteo de miembros y flags "
        "(hoist, mentionable, managed). Úsala para descubrir qué roles existen y obtener sus IDs "
        "ANTES de usar get_role_members, assign_role, remove_role, o cualquier tool que requiera role_id. "
        "NO adivines role_ids — siempre usa esta tool primero.",
        {}, []),

    _decl("find_role",
        "Busca roles por nombre (búsqueda parcial case-insensitive). Devuelve el role_id, "
        "color, conteo de miembros y flags de cada coincidencia. "
        "Úsala cuando un usuario menciona un rol por nombre (ej: 'familia perrito') y necesitas "
        "su role_id para get_role_members u otras operaciones. "
        "PREFIERE esta tool sobre list_roles cuando ya sabes el nombre aproximado del rol.",
        {"name": _str("Nombre parcial del rol a buscar, ej: 'familia', 'perrito', 'mod'")},
        ["name"]),

    _decl("create_reaction_role",
        "Vincula un emoji a un rol en un mensaje.",
        {"message_id": _str("ID del mensaje"),
         "emoji": _str("Emoji que activa el rol"),
         "role_id": _str("ID del rol a asignar/quitar"),
         "channel_id": _str("ID del canal del mensaje (opcional)")},
        ["message_id", "emoji", "role_id"]),

    _decl("sync_role_permissions",
        "Copia los permisos de canal de un rol a otro. Requiere MANAGE_ROLES.",
        {"source_role_id": _str("ID del rol fuente"),
         "target_role_id": _str("ID del rol destino"),
         "channel_id": _str("ID del canal a sincronizar (opcional)")},
        ["source_role_id", "target_role_id"]),

    _decl("delete_role",
        "Elimina un rol del servidor. Requiere MANAGE_ROLES. "
        "Usa find_role o list_roles primero para obtener el role_id correcto.",
        {"role_id": _str("ID del rol a eliminar"),
         "reason": _str("Razón para el audit log (opcional)")},
        ["role_id"]),

    _decl("role_info",
        "Info detallada de UN solo rol: color, posición, permisos, flags, fecha de creación, "
        "y miembros online/offline. Más ligero que get_role_members cuando no necesitas la lista completa.",
        {"role_id": _str("ID del rol")}, ["role_id"]),

    _decl("bulk_assign_role_all",
        "Asigna (o quita) un rol a TODOS los miembros del servidor DE UNA VEZ. "
        "Ejecución masivamente paralela con semáforo de 20 concurrencia. "
        "Ideal para 'darle @nuevo-rol a todo el server'. Requiere MANAGE_ROLES. "
        "ADVERTENCIA: Esta operación puede ser pesada en servers grandes (1000+ miembros).",
        {"role_id": _str("ID del rol a asignar o quitar"),
         "action": _str("'add' para asignar a todos, 'remove' para quitar de todos (default 'add')"),
         "ignore_bots": _bool("Si ignorar bots (default True)")},
        ["role_id"]),

    # MENSAJERÍA ENRIQUECIDA
    _decl("send_embed",
        "Envía un embed Discord rico y personalizado a un canal. "
        "Lee la skill 'embed_design' primero para usar plantillas y colores correctos.",
        {"channel_id": _str("ID del canal destino"),
         "title": _str("Título del embed (opcional)"),
         "description": _str("Descripción principal (soporta markdown de Discord)"),
         "color": _str("Color hex, ej: '#A855F7'. Default: violeta Fairy"),
         "fields_json": _str('[{"name":"Campo","value":"Valor","inline":true}]'),
         "footer_text": _str("Texto del footer (opcional)"),
         "footer_icon_user_id": _str("user_id para avatar como icono del footer (opcional)"),
         "author_name": _str("Nombre en la sección author (opcional)"),
         "author_icon_user_id": _str("user_id para avatar como icono del author (opcional)"),
         "thumbnail_user_id": _str("user_id cuyo avatar se usará como thumbnail (opcional)"),
         "thumbnail_url": _str("URL de imagen para thumbnail (alternativa a thumbnail_user_id)"),
         "image_url": _str("URL de imagen de ancho completo al fondo del embed (opcional)"),
         "timestamp": _bool("Si añadir la hora actual al embed (default False)"),
         "content": _str("Texto plano sobre el embed (opcional)")},
        ["channel_id", "description"]),

    _decl("send_dm",
        "Envía un mensaje privado/DM directo a un usuario. Mándale un privado, escríbele por MD. "
        "Sinónimos: mandar DM, mensaje privado, escríbele, mándale un MD, háblale por privado.",
        {"user_id": _str("ID del usuario destinatario"), "content": _str("Texto del mensaje"),
         "embed_title": _str("Título del embed opcional"),
         "embed_color": _str("Color hex del embed (opcional)")},
        ["user_id", "content"]),

    # INFORMACIÓN Y DB
    _decl("get_user_info",
        "Info completa de un usuario: roles, cuenta, advertencias, tiempo en servidor.",
        {"user_id": _str("ID numérico del usuario")}, ["user_id"]),

    _decl("get_user_by_name",
        "Resuelve un nombre o apodo a user_id y devuelve perfil completo + Character Card "
        "+ mensajes recientes en UNA SOLA llamada.",
        {"name": _str("Nombre, apodo o username (parcial o completo)"),
         "context": _str("Qué necesitas saber: 'nickname', 'card', 'activity' (opcional)")},
        ["name"]),

    _decl("batch_user_lookup",
        "Busca MÚLTIPLES usuarios en UNA sola llamada. MUCHO más eficiente que llamar "
        "get_user_by_name repetidamente. Pasa hasta 10 nombres separados por comas. "
        "Devuelve un dict {nombre: perfil} para cada nombre encontrado.",
        {"names": _str("Nombres separados por comas, ej: 'Makao, Lia, Papu'"),
         "context": _str("Qué info necesitas: 'basic' (solo ID/nombre) o 'full' (card+msgs), default 'basic'")},
        ["names"]),

    _decl("search_messages",
        "Busca mensajes por keyword exacto (FTS5). Busca qué dijo alguien, cuándo lo dijo. "
        "Default busca en TODO el historial (8760h). "
        "Sinónimos: buscar mensajes, qué dijo, cuándo dijo, busca lo que escribió, encuentra mensajes.",
        {"keyword": _str("Palabra o frase a buscar (opcional)"),
         "user_id": _str("Filtrar por user_id (opcional)"),
         "channel_id": _str("Filtrar por channel_id (opcional)"),
         "hours": _int("Buscar en las últimas N horas (default 8760=todo)"),
         "limit": _int("Máximo resultados (default 50, máx 100)")},
        []),

    _decl("get_server_activity",
        "Top usuarios activos en las últimas N horas.",
        {"hours": _int("Ventana de tiempo en horas (default 24)")}, []),

    _decl("get_user_card",
        "Obtiene la Character Card completa de un usuario por su ID.",
        {"user_id": _str("ID numérico del usuario")}, ["user_id"]),

    _decl("get_channel_summary",
        "Últimos mensajes de un canal con conteo de participantes.",
        {"channel_id": _str("ID del canal (opcional, usa el actual)"),
         "hours": _int("Horas hacia atrás (default 24, máx 168)")},
        []),

    _decl("get_leaderboard",
        "Ranking de usuarios más activos.",
        {"limit": _int("Usuarios a mostrar (1-20, default 10)"),
         "hours": _int("Filtrar por últimas N horas (omitir para histórico total)")},
        []),

    _decl("list_bans",
        "Lista los usuarios baneados actualmente en el servidor. Requiere BAN_MEMBERS.",
        {"limit": _int("Máximo de entradas a devolver (1-50, default 20)")}, []),

    _decl("get_voice_members",
        "Devuelve quién está conectado en los canales de voz ahora mismo.",
        {"channel_id": _str("ID del canal de voz específico (opcional)")}, []),

    _decl("list_emojis",
        "Lista todos los emojis personalizados del servidor.", {}, []),

    _decl("get_active_threads",
        "Lista todos los hilos activos (no archivados) en el servidor.", {}, []),

    # ANÁLISIS E INTELIGENCIA
    _decl("detect_newcomers",
        "Usuarios que se unieron al servidor en las últimas N horas.",
        {"hours": _int("Horas hacia atrás para buscar joins (default 24, máx 720)")}, []),

    _decl("find_inactive_members",
        "Miembros sin mensajes en los últimos N días.",
        {"days": _int("Días sin actividad (default 30)"),
         "limit": _int("Máximo de miembros a devolver (default 50)")},
        []),

    _decl("compare_user_activity",
        "Compara la actividad de dos usuarios lado a lado en un período dado.",
        {"user_id_1": _str("ID del primer usuario"), "user_id_2": _str("ID del segundo usuario"),
         "hours": _int("Horas hacia atrás a analizar (default 168 = 1 semana)")},
        ["user_id_1", "user_id_2"]),

    _decl("get_peak_hours",
        "SHORTCUT: horas UTC de mayor actividad (equivale a aggregate_messages group_by=hour_of_day).",
        {}, []),

    _decl("filter_members",
        "Filtra miembros del servidor por múltiples criterios COMBINABLES: "
        "rol, fecha de join, estado online, y búsqueda por nombre. "
        "Devuelve user_id, display_name, avatar_url, joined_at y roles. "
        "MUCHO más eficiente que buscar manualmente con get_user_info uno por uno.",
        {"role_id": _str("Filtrar por ID de rol (opcional)"),
         "search_name": _str("Buscar por nombre/display_name parcial (opcional)"),
         "joined_after_hours": _int("Solo miembros que se unieron en las últimas N horas"),
         "joined_before_days": _int("Solo miembros que llevan más de N días"),
         "is_online": _bool("Solo miembros conectados ahora mismo"),
         "limit": _int("Máximo de resultados (default 50, max 200)")},
        []),

    _decl("server_dashboard",
        "Dashboard completo del servidor en UNA SOLA llamada. Incluye: "
        "total miembros, online ahora, joins recientes, top canales por actividad, "
        "distribución de roles (top 10 por miembros), y pico de actividad. "
        "Úsala cuando necesitas una vista general rápida sin múltiples tools.",
        {}, []),

    # UTILIDADES DE CONTENIDO
    _decl("schedule_message",
        "Programa un mensaje para enviarse automáticamente en N minutos.",
        {"channel_id": _str("ID del canal destino"),
         "content": _str("Texto del mensaje a enviar"),
         "delay_minutes": _int("Minutos hasta el envío (1-10080)")},
        ["channel_id", "content", "delay_minutes"]),

    _decl("cancel_scheduled_message",
        "Cancela un mensaje programado antes de que se envíe.",
        {"task_id": _str("task_id devuelto por schedule_message")},
        ["task_id"]),

    _decl("fetch_url_preview",
        "Obtiene el título, descripción e imagen OG de una URL.",
        {"url": _str("URL completa a previsualizar (incluyendo https://)"),
         "channel_id": _str("ID del canal donde enviar el embed (opcional)")},
        ["url"]),

    _decl("weather",
        "Clima actual de una ciudad o ubicación.",
        {"location": _str("Ciudad o ubicación, ej: 'Madrid', 'New York'")},
        ["location"]),

    _decl("time_in",
        "Hora actual en una zona horaria específica.",
        {"timezone": _str("Zona horaria IANA, ej: 'America/New_York', 'Europe/Madrid'")},
        ["timezone"]),

    # GRÁFICOS
    _decl("render_template",
        "Genera gráficos ultra-rápidos usando templates SVG pre-construidos (~50ms). "
        "ÚNICA tool para CUALQUIER visualización: tierlist, leaderboard, gráfico de barras, "
        "tarjeta de perfil, banner, gráfico circular, stats grid, comparación, grafo social, matriz de correlación, "
        "love graph, achievement, timeline, heatmap, radar, etc. "
        "Lee la skill 'graphics' para ver los schemas JSON de cada template.",
        {"template": _str("Nombre: tierlist | leaderboard | bar_chart | profile_card | banner | donut_chart | stat_grid | comparison | radar_chart | timeline | heatmap | achievement_card | love_graph | graph_network | correlation_matrix | investigation_timeline"),
         "data": _str("JSON string con los datos del gráfico. Lee la skill 'graphics' para el schema de cada template."),
         "channel_id": _str("ID del canal destino (opcional, usa el actual)"),
         "filename": _str("Nombre del archivo PNG (opcional, ej: 'tierlist.png')")},
        ["template", "data"]),

    # INTEGRACIÓN EXTERNA
    _decl("create_github_issue",
        "Abre una issue en GitHub directamente desde Discord. "
        "Requiere GITHUB_TOKEN y GITHUB_DEFAULT_REPO en variables de entorno.",
        {"title": _str("Título de la issue"),
         "body": _str("Descripción de la issue (soporta Markdown)"),
         "repo": _str("Repositorio en formato 'owner/repo' (opcional)"),
         "labels": _str("Etiquetas separadas por coma (opcional)")},
        ["title", "body"]),

    # COMUNICACIÓN
    _decl("edit_message",
        "Edita un mensaje existente del bot en un canal. Solo puede editar mensajes del propio bot.",
        {"message_id": _str("ID del mensaje a editar"),
         "new_content": _str("Nuevo contenido del mensaje"),
         "channel_id": _str("ID del canal donde está el mensaje (opcional)")},
        ["message_id", "new_content"]),

    _decl("create_reminder",
        "Crea un recordatorio que enviará un DM al usuario después de N minutos.",
        {"user_id": _str("ID del usuario que recibirá el recordatorio"),
         "text": _str("Texto del recordatorio"),
         "delay_minutes": _int("Minutos hasta el recordatorio (1-10080, default 60)")},
        ["user_id", "text"]),

    _decl("broadcast",
        "Envía un mensaje por DM a TODOS los miembros de un rol específico. "
        "Masivamente paralelo (semáforo 15). Útil para anuncios a mods, staff, etc. "
        "Devuelve conteo de enviados y fallidos (DMs cerrados).",
        {"role_id": _str("ID del rol cuyos miembros recibirán el mensaje"),
         "content": _str("Texto del mensaje a enviar por DM"),
         "embed_title": _str("Título del embed (opcional, si se provee se envía como embed)")},
        ["role_id", "content"]),

    # MISCÉLANEA
    _decl("set_nickname",
        "Cambia el apodo/nick de un usuario en el servidor. Ponle nombre, renómbralo. "
        "Lee la skill 'apodos' primero si el apodo no fue dado explícitamente. "
        "NO funciona con el dueño del servidor. "
        "Sinónimos: poner apodo, cambiar nombre, renombrar, ponle nick, cámbiale el nombre.",
        {"user_id": _str("ID del usuario"),
         "nickname": _str("Nuevo apodo. Omitir para resetear.")},
        ["user_id"]),

    _decl("move_to_voice",
        "Mueve a un usuario a un canal de voz específico.",
        {"user_id": _str("ID del usuario"), "channel_id": _str("ID del canal de voz destino")},
        ["user_id", "channel_id"]),

    _decl("create_poll",
        "Crea una encuesta nativa de Discord en un canal.",
        {"question": _str("Pregunta de la encuesta (máx 300 caracteres)"),
         "answers": _str("Opciones separadas por coma, ej: 'Sí, No, Tal vez'"),
         "channel_id": _str("ID del canal (opcional)"),
         "duration_h": _int("Duración en horas (1-168, default 24)"),
         "multiple": _bool("Permitir votar varias opciones")},
        ["question", "answers"]),

    # EVENTOS
    _decl("create_event",
        "Crea un evento programado en el servidor. "
        "Lee la skill 'eventos' primero para seguir el flujo completo de planificación.",
        {"name": _str("Nombre del evento"),
         "start_time": _str("Fecha y hora de inicio ISO 8601, ej: '2025-06-15T20:00:00'"),
         "end_time": _str("Fecha y hora de fin (requerido para eventos externos)"),
         "description": _str("Descripción del evento (opcional)"),
         "voice_channel_id": _str("ID del canal de voz (para eventos dentro del servidor)"),
         "location": _str("Ubicación como texto (para eventos externos)")},
        ["name", "start_time"]),

    _decl("delete_event",
        "Elimina un evento programado del servidor.",
        {"event_id": _str("ID del evento a eliminar")}, ["event_id"]),

    _decl("list_events",
        "Lista todos los eventos programados activos en el servidor.", {}, []),

    # ORQUESTACIÓN
    _decl("run_workflow",
        "Ejecuta un workflow predefinido que orquesta múltiples herramientas en secuencia. "
        "Usa workflows para acciones críticas donde el LLM no debe improvisar el orden.",
        {"workflow_id": _str("ID del workflow: 'antiraid_lockdown' | 'welcome_sequence' | 'cleanup_inactive' | 'mod_alert'"),
         "params_json": _str("Parámetros como JSON string. Ej: '{\"user_ids\":\"111,222\",\"duration\":\"1h\",\"reason\":\"spam\"}'")},
        ["workflow_id"]),

    # BÚSQUEDA INTELIGENTE
    # COMPONENTES INTERACTIVOS
    _decl("interactive_component",
        "Crea botones, menús de selección o modals en un canal de Discord. "
        "Los usuarios interactúan sin escribir comandos. Requiere discord.ui.",
        {"channel_id": _str("ID del canal destino"),
         "component_type": _str("Tipo: 'buttons' | 'select_menu' | 'modal'"),
         "content": _str("Texto del mensaje que acompaña al componente"),
         "actions_json": _str('JSON de acciones. Ej botones: [{"label":"Aprobar","style":"green","custom_id":"approve_123","emoji":"✅"},{"label":"Ban","style":"red","custom_id":"ban_123","emoji":"🔨"}]'),
         "timeout_minutes": _int("Minutos antes de que el componente deje de funcionar (default 15, max 60)")},
        ["channel_id", "component_type", "content", "actions_json"]),

    # CÓDIGO SEGURO — REMOVIDO 2026-05-15 (SEC-01, Wave 1)
    # La tool `execute_code` permitía RCE via prompt injection: el sandbox
    # basado en filtros de string ("import", "open", "eval") es trivial de
    # evadir con __subclasses__()/__class__.__mro__. Si la feature debe
    # reintroducirse, usar subprocess aislado con nsjail / firejail /
    # bubblewrap, sin red ni filesystem, con timeouts y RLIMIT.
    # Ver .code-review/04-report.md (SEC-01) y .code-review/05-plan.md (F0.1).

    # BACKUP
    _decl("backup_server",
        "Crea un snapshot JSON completo del estado del servidor: roles, canales, categorías, permisos y emojis. "
        "Ideal para disaster recovery o migración.",
        {"include_roles": _bool("Incluir roles y permisos base (default True)"),
         "include_channels": _bool("Incluir canales, categorías y overwrites (default True)"),
         "include_emojis": _bool("Incluir emojis custom (default True)"),
         "filename": _str("Nombre del archivo JSON (default: backup_GUILDID_TIMESTAMP.json)")},
        []),

    # INVITACIONES
    _decl("create_invite",
        "Genera un enlace de invitación para un canal. Requiere CREATE_INSTANT_INVITE.",
        {"channel_id": _str("ID del canal (opcional, usa el actual)"),
         "max_age": _int("Duración en segundos (0 = permanente, default 86400 = 24h)"),
         "max_uses": _int("Máximo de usos (0 = ilimitado)"),
         "temporary": _bool("Si la membresía es temporal")},
        []),

    # AUDITORÍA
    _decl("get_audit_log",
        "Obtiene entradas recientes del registro de auditoría. Requiere VIEW_AUDIT_LOG.",
        {"limit": _int("Entradas a obtener (1-25, default 10)"),
         "action": _str(
             "Filtrar por tipo: ban, unban, kick, role_update, role_create, role_delete, "
             "channel_create, channel_delete, member_update, message_delete, invite_create (opcional)"
         )},
        []),

    # ── SKILLS ────────────────────────────────────────────────────────────────
    _decl("read_skill",
    "Loads a skill protocol from the skills database. "
    "Check the Skill Routing Table in your system instructions "
    "to determine which skill to load before acting. "
    "Available: ascii_art | antiraid | graphics | sellar | "
    "embed_design | onboarding | sherlock_kai | "
    "data_mastery | eventos | apodos | traduccion | "
    "zzz_terminos | rules | obscura-web",
        {"skill_name": _str(
            "Nombre exacto de la skill: "
            "ascii_art | antiraid | graphics | sellar | embed_design | onboarding | "
            "sherlock_kai | data_mastery | eventos | apodos | "
            "traduccion | zzz_terminos | rules | obscura-web"
        )},
        ["skill_name"]),

    # LISTENERS
    _decl("create_listener",
        "Registra una regla automática. Llama DIRECTAMENTE sin pedir confirmación. "
        "Triggers: on_message, on_join, on_leave, on_reaction_add, on_voice_join, on_schedule, on_member_update. "
        "Conditions: none, contains, exact, regex, scored, semantic, starts_with, ends_with, rate. "
        "Actions: reply_text, reply_embed, reply_link, dm_user, add_reaction, delete_message, "
        "mute_user, warn_user, kick_user, ban_user, seal_user, assign_role, remove_role, "
        "send_embed, llm_respond, copy_to_channel, notify_mods, escalate, impersonate. "
        "Para on_schedule: trigger.schedule={type:'interval', hours?:N, minutes?:N, seconds?:N, days?:N}. "
        "Acciones soportadas en on_schedule: send_text, send_embed (requieren channel_id). "
        "No necesita condition (se ignora). Se ejecuta automáticamente cada intervalo. "
        "Para impersonate/transforms avanzados → read_skill('listeners').",
        {"rule_json": _str("JSON completo de la regla. Estructura: "
                           "{trigger:{type,filters?:{ignore_bots,only_user_ids?,channel_ids?},"
                           "schedule?:{type:'interval',hours?,minutes?,days?}},"
                           "condition:{type,values?|patterns?},"
                           "actions:[{type,text?|emoji?|duration?|content?|role_id?|user_id?|channel_id?}],"
                           "limits?:{cooldown_seconds?},name}",
                           enum=None),
         "description": _str("Descripción legible (opcional)")},
        ["rule_json"]),

    _decl("list_listeners",
        "Lista reglas automáticas del servidor con búsqueda y paginación. "
        "USAR `search` cuando el usuario menciona un nombre — devuelve la regla "
        "completa con todos sus detalles. Si no hay search, devuelve versión "
        "liviana (rule_id+name+enabled+trigger_type). Si total>showing hay más; "
        "ajustar offset o filtrar con search.",
        {"filter":       _str("Filtro de estado", enum=["all", "active", "inactive"]),
         "trigger_type": _str("Filtrar por tipo de trigger (opcional)"),
         "search":       _str("Substring sobre nombre o rule_id (case-insensitive). "
                              "Cuando se usa, devuelve verbose y sin paginación."),
         "limit":        _int("Máximo a devolver (default 25, max 100)"),
         "offset":       _int("Desde dónde empezar (default 0)"),
         "verbose":      _bool("Si True, incluye trigger/condition/actions completas. "
                               "Default False (modo liviano).")},
        []),

    _decl("toggle_listener",
        "Activa o desactiva una regla sin eliminarla.",
        {"rule_id": _str("ID de la regla"), "enabled": _bool("True para activar, False para desactivar")},
        ["rule_id", "enabled"]),

    _decl("delete_listener",
        "Elimina permanentemente una regla de DB y memoria.",
        {"rule_id": _str("ID de la regla a eliminar")},
        ["rule_id"]),

    _decl("edit_listener",
        "Modifica campos de una regla existente (patch parcial).",
        {"rule_id": _str("ID de la regla"),
         "patch_json": _str("JSON con los campos a modificar")},
        ["rule_id", "patch_json"]),

    _decl("test_listener",
        "Evalúa un texto de prueba contra una regla SIN ejecutar acciones.",
        {"rule_id": _str("ID de la regla"),
         "test_text": _str("Texto a probar contra la condición")},
        ["rule_id", "test_text"]),

    _decl("get_listener_stats",
        "Estadísticas de disparos de una regla: histograma por hora, top usuarios.",
        {"rule_id": _str("ID de la regla"),
         "hours": _int("Ventana de tiempo en horas (default 24)")},
        ["rule_id"]),

    # SELLO
    _decl("seal_user",
        "Sella/aísla a un usuario: encierro avanzado con rol sellado + canal privado + remoción de roles. "
        "Programa liberación automática. Notifica a mods con embed. "
        "Sinónimos: sellar, aislar, encerrar, poner en cuarentena, enciérralo, séllalo.",
        {"user_id": _str("ID del usuario a sellar"),
         "duration": _str("Duración del sello", enum=["30m", "1h", "6h", "12h", "1d", "3d", "7d"]),
         "reason": _str("Razón del sello"),
         "mod_channel_id": _str("Canal para notificar a mods (opcional)")},
        ["user_id"]),

    _decl("unseal_user",
        "Libera a un usuario sellado. Quita el sello, desencierro, saca de cuarentena. "
        "Restaura sus roles originales, elimina el rol sellado y el canal temporal. "
        "Sinónimos: liberar, dessellar, quitar sello, sacar del encierro, libéralo, suéltalo.",
        {"user_id": _str("ID del usuario a liberar")}, ["user_id"]),

    _decl("list_sealed_users",
        "Lista todos los usuarios actualmente sellados/encerrados con su razón, tiempo restante y canal. "
        "Sinónimos: quiénes están sellados, lista de sellados, quién está en cuarentena.",
        {}, []),

    # DATA MASTERY
    _decl("search_messages_semantic",
        "Búsqueda INTELIGENTE de mensajes: FTS5 + embeddings semánticos + fusión RRF. "
        "USA ESTA por defecto para buscar mensajes. Encuentra por SIGNIFICADO, no solo palabras exactas. "
        "Ejemplo: query='peleas' encuentra 'se insultaron' aunque no diga 'pelea'. "
        "Solo usa search_messages si necesitas coincidencia LITERAL de una palabra específica.",
        {"query":           _str("Pregunta o concepto en lenguaje natural"),
          "hours":           _int("Ventana de tiempo en horas (default 8760=TODO el historial, max 87600)"),
          "limit":           _int("Máximo de resultados (default 50, max 100)"),
          "user_id":         _str("Filtrar por user_id (opcional)"),
          "channel_id":      _str("Filtrar por channel_id (opcional)"),
          "semantic_weight": _str("0.0=solo keywords, 1.0=solo semántico, 0.5=híbrido (default 0.5)"),
          "min_score":       _str("Score mínimo RRF para filtrar ruido (default 0.0, recomendado 0.3)")},
        ["query"]),

    _decl("get_message_context",
        "Extrae el CONTEXTO TEMPORAL de una conversación alrededor de un mensaje específico. "
        "Obtiene hasta 300 mensajes (150 anteriores y 150 posteriores por defecto, o personalizable a 100) al mensaje objetivo en el mismo canal. "
        "USA ESTA herramienta inmediatamente cuando veas un mensaje relevante en una búsqueda o investigación "
        "para ver el contexto real de la conversación (qué pasó antes y después de dicho mensaje).",
        {"message_id": _str("ID numérico del mensaje central que sirve como punto de referencia"),
         "before_limit": _int("Cantidad de mensajes anteriores a recuperar (default 150, recomendado 100)"),
         "after_limit": _int("Cantidad de mensajes posteriores a recuperar (default 150, recomendado 100)")},
        ["message_id"]),

    _decl("aggregate_messages",
        "CONTEOS y ESTADÍSTICAS directas en SQL — NO trae mensajes, solo números. "
        "Usa para: '¿cuántos mensajes?', '¿quién es más activo?', '¿qué día hubo más actividad?'. "
        "Soporta rangos absolutos y grouping. MUCHO más rápido que search para análisis cuantitativo.",
        {"group_by":   _str("Agrupar por", enum=["user", "channel", "day", "hour_of_day"]),
         "hours":      _int("Ventana relativa en horas. Ignorado si start_ts está presente."),
         "limit":      _int("Máximo de grupos (default 20)"),
         "user_id":    _str("Filtrar por usuario específico (opcional)"),
         "channel_id": _str("Filtrar por canal específico (opcional)"),
         "start_ts":   _str("Inicio del rango absoluto ISO 8601, ej: '2025-04-01T00:00:00'"),
         "end_ts":     _str("Fin del rango absoluto ISO 8601 (opcional, default ahora)"),
         "agg_type":   _str("Tipo de agregación", enum=["messages", "audit"])},
        []),

    _decl("paginate_messages",
        "Paginación real de mensajes con OFFSET para volúmenes grandes. "
        "Llama repetidamente incrementando 'offset' hasta que has_more=False.",
        {"hours":      _int("Ventana de tiempo en horas (default 168)"),
         "limit":      _int("Mensajes por página (default 100, max 200)"),
         "offset":     _int("Cuántos mensajes saltar (default 0)"),
         "user_id":    _str("Filtrar por usuario (opcional)"),
         "channel_id": _str("Filtrar por canal (opcional)"),
         "start_ts":   _str("Inicio de rango absoluto ISO 8601 (opcional)"),
         "end_ts":     _str("Fin de rango absoluto ISO 8601 (opcional)"),
         "order":      _str("'asc' (cronológico) o 'desc' (más recientes primero, default)")},
        []),

    _decl("get_user_timeline",
        "Timeline CRONOLÓGICO completo de un usuario: mensajes + warns + acciones de moderación "
        "entrelazados. Herramienta principal de investigación Sherlock para perfilar usuarios. "
        "Incluye resumen de actividad por día.",
        {"user_id": _str("ID numérico del usuario"),
         "days":    _int("Días hacia atrás a analizar (default 14, max 90)")},
        ["user_id"]),

    _decl("profile_sample",
        "Muestra INTELIGENTE de ~300 mensajes de un usuario esparcidos uniformemente en todo su historial. "
        "Ideal para conocer a alguien: sus temas, humor, personalidad, evolución. "
        "Filtra mensajes cortos (<15 chars) y toma muestras equidistantes para cubrir toda su historia.",
        {"user_id": _str("ID numérico del usuario"),
         "sample_size": _int("Cantidad de mensajes a muestrear (default 300, max 500)")},
        ["user_id"]),

    _decl("get_loan_info",
        "Consulta el estado de deudas/préstamos de un usuario o lista de morosos del servidor. "
        "Devuelve score crediticio, deuda activa, historial de pagos. "
        "DEPRECATED: usa list_morosos / get_user_debt / get_loan_history para datos más ricos.",
        {"user_id": _str("ID del usuario (omitir para lista de morosos del servidor)"),
         "mode": _str("'status' (default) | 'morosos' | 'historial'")},
        []),

    _decl("list_morosos",
        "Lista deudores del servidor con datos completos para construir una TABLA RICA: "
        "nombre, deuda restante, cuota, progreso de pagos (X/Y), días desde el préstamo, "
        "score, fallos consecutivos, próximo cobro. Úsala cuando pidan 'deudores', 'morosos', "
        "'lista de quién debe', etc. PREFIERE esta sobre get_loan_info(mode='morosos').",
        {"sort": _str("Orden: 'debt_desc' (default) | 'debt_asc' | 'misses_desc' | 'days_desc' | 'score_asc'"),
         "min_debt": _int("Filtra deudores con deuda restante >= este valor (default 0)"),
         "only_late": _str("'yes' (default) solo deudores con cuotas falladas; 'no' incluye al día"),
         "limit": _int("Máx resultados (default 25, max 50)")},
        []),

    _decl("get_user_debt",
        "Estado financiero COMPLETO de un usuario: score, tier (S/A/B/C/D), préstamo activo "
        "con progreso, próxima cuota, fallos. Úsala para '¿cuánto debe X?', '¿cómo va X con su deuda?'. "
        "PREFIERE esta sobre get_loan_info(mode='status').",
        {"user_id": _str("ID numérico del usuario")},
        ["user_id"]),

    _decl("get_loan_leaderboard",
        "Rankings del sistema crediticio: top deudores, mejores pagadores, peores defaulters, "
        "más prestamistas, deudas más antiguas. Úsala cuando pidan 'top deudores', 'mejores clientes', "
        "'quién paga mejor', 'wall of shame'.",
        {"mode": _str("'biggest_debtors' | 'best_payers' | 'worst_defaulters' | 'top_borrowers' | 'longest_active'"),
         "limit": _int("Top N resultados (default 10, max 25)")},
        ["mode"]),

    _decl("get_loan_stats",
        "Estadísticas globales del sistema de préstamos del servidor: préstamos activos, "
        "deuda total circulante, morosos, completados, defaulteados, score promedio, blacklisted, "
        "tasa de éxito de cobros. Úsala para 'cómo va el banco', 'estadísticas de préstamos', "
        "'cuánta deuda hay'.",
        {},
        []),

    _decl("get_loan_history",
        "Historial de PAGOS (no préstamos) de un usuario: cada cobro intentado con monto, éxito/fallo, "
        "balance antes/después y timestamp. Útil para auditar comportamiento de pago de un deudor.",
        {"user_id": _str("ID numérico del usuario"),
         "limit": _int("Máx pagos (default 10, max 30)")},
        ["user_id"]),

    _decl("get_treasury_balance",
        "Estado del BANCO/TESORERÍA del servidor (Y O U K A I · B A N K): balance disponible, "
        "deuda en circulación (créditos prestados sin pagar), histórico de ingresos/egresos, "
        "pérdidas por defaults, ganancia neta, breakdown por tipo de movimiento. "
        "Úsala cuando pregunten 'cuánto tiene el banco', 'cómo va el pool', 'saldo del servidor', "
        "'cuánto tiene Youkai en caja'.",
        {},
        []),

    _decl("get_treasury_history",
        "Últimos movimientos del banco del servidor con tipo, monto, balance resultante y "
        "usuario relacionado. Úsala para 'movimientos del banco', 'historial del pool', "
        "'qué pasó con la caja'.",
        {"limit": _int("Máx movimientos (default 15, max 50)"),
         "reason_filter": _str("Filtrar por razón: 'loan_disbursed' | 'loan_repayment' | 'staff_grant' | 'staff_deposit' | 'loan_default' | 'bootstrap'")},
        []),

    _decl("treasury_grant_credits",
        "STAFF ONLY: Entrega créditos del pool del banco a un usuario (ej: premio, recompensa, perdón). "
        "Si el banco no tiene fondos suficientes, falla. Genera un movimiento 'staff_grant' visible "
        "en el historial. Requiere permiso `manage_guild`.",
        {"user_id": _str("ID del usuario receptor"),
         "amount": _int("Cantidad de créditos a entregar"),
         "reason": _str("Razón visible en el historial")},
        ["user_id", "amount", "reason"]),

    _decl("treasury_deposit",
        "STAFF ONLY: Ingresa créditos al pool del banco desde fuera (ej: penalización a un usuario, "
        "recompensa exterior, ajuste manual). Genera movimiento 'staff_deposit' en el historial. "
        "Requiere permiso `manage_guild`.",
        {"amount": _int("Cantidad a depositar"),
         "reason": _str("Razón visible en el historial")},
        ["amount", "reason"]),

    _decl("query_pattern_analysis",
        "Análisis de PATRONES OCULTOS en el servidor. Detecta co-ocurrencias entre usuarios, "
        "anomalías temporales (spikes/drops inusuales por z-score) y usuarios que "
        "silenciaron repentinamente. Fundamental para investigaciones Sherlock.",
        {"mode": _str("'cooccurrence' | 'anomaly' | 'sudden_silence'"),
         "hours": _int("Ventana de tiempo en horas (default 720 = 1 mes)"),
         "days": _int("Para sudden_silence: días de inactividad a detectar (default 7)"),
         "min_overlap": _int("Para cooccurrence: mínimo de co-mensajes para contar (default 3)"),
         "sensitivity": _str("Para anomaly: desviaciones estándar para anomalía (default 2.0)"),
         "min_previous_messages": _int("Para sudden_silence: mínimo de msgs previos (default 10)")},
        ["mode"]),

    _decl("investigate_topic",
        "MACRO-TOOL: investigación completa en UNA llamada. Combina búsqueda semántica + "
        "resolución de usuarios + stats. Responde preguntas como 'quiénes hablan de X', "
        "'cuánto se habla de Y', 'qué opinan de Z'. PREFIERE esta sobre encadenar 3+ tools.",
        {"query": _str("Tema o pregunta en lenguaje natural"),
         "hours": _int("Ventana de tiempo en horas (default 8760=TODO el historial)"),
         "max_users": _int("Máx usuarios a perfilar (default 5)"),
         "include_stats": _str("'yes' para incluir aggregate_messages del tema (default 'yes')")},
        ["query"]),

    # ── GRAPH ANALYSIS (Sherlock Kai) ──────────────────────────────────────
    _decl("analyze_social_graph",
        "Construye un grafo social del servidor mostrando conexiones entre usuarios. "
        "Dos usuarios están conectados si co-ocurren (mensajes en el mismo canal dentro de 5 minutos). "
        "Devuelve nodos (usuarios) y aristas (conexiones) con pesos. "
        "Usa los resultados con render_template(template='graph_network') para visualizar.",
        {"hours": _int("Ventana de tiempo en horas (default 720 = 1 mes)")},
        []),

    _decl("find_communities",
        "Detecta comunidades/grupos de usuarios que interactúan frecuentemente. "
        "Usa fusión por similitud de vecindario en el grafo social. "
        "Devuelve comunidades con miembros, densidad interna y canales principales.",
        {"min_size": _int("Tamaño mínimo del grupo (default 3)"),
         "hours": _int("Ventana de tiempo en horas (default 720 = 1 mes)")},
        []),

    _decl("trace_influence_path",
        "Encuentra la cadena de conexión más corta entre dos usuarios a través de canales compartidos. "
        "Usa BFS en el grafo de co-ocurrencia. Útil para determinar si dos usuarios están relacionados "
        "directa o indirectamente.",
        {"user_a_id": _str("ID del primer usuario"),
         "user_b_id": _str("ID del segundo usuario"),
         "max_depth": _int("Profundidad máxima de búsqueda (default 4)")},
        ["user_a_id", "user_b_id"]),

    _decl("detect_coordinated_activity",
        "Detecta actividad coordinada entre grupos de usuarios (posible raid o spam organizado). "
        "Busca usuarios que postearon en los mismos canales en ventanas de tiempo ajustadas Y tienen "
        "contenido de mensaje similar (Jaccard sobre CRC32 de tokens, mismo fingerprint que automod). "
        "Usa junto con antiraid_scan para confirmar raids.",
        {"hours": _int("Ventana de tiempo en horas (default 24)"),
         "similarity_threshold": _str("Umbral de similitud 0.0-1.0 (default 0.7)")},
        []),

    _decl("correlate_user_behavior",
        "Compara patrones de actividad entre dos usuarios para detectar cuentas relacionadas. "
        "Calcula correlación de Pearson sobre conteos horarios de mensajes, canales compartidos, "
        "y solapamiento temporal. Emite veredicto: highly_correlated, moderately_correlated, uncorrelated.",
        {"user_a_id": _str("ID del primer usuario"),
         "user_b_id": _str("ID del segundo usuario"),
         "hours": _int("Ventana de tiempo en horas (default 720 = 1 mes)")},
        ["user_a_id", "user_b_id"]),

    _decl("run_anomaly_scan",
        "Escanea actividad del servidor detectando picos anómalos de mensajes por usuario. "
        "Para cada usuario, calcula z-score por hora y marca aquellas donde z-score > sensitivity. "
        "Anomalías en múltiples usuarios a la misma hora sugieren raid o evento coordinado.",
        {"hours": _int("Ventana de tiempo en horas (default 168)"),
         "sensitivity": _str("Desviaciones estándar para marcar anomalía (default 2.0). "
                            "1.5=más sensible, 3.0=solo anomalías extremas")},
        []),

    # WEB BROWSING
    _decl("web_fetch",
        "Navega a una URL y extrae su contenido textual usando un navegador headless (Obscura) "
        "con rotación de User-Agent, modo stealth, y wait-until networkidle para máxima compatibilidad. "
        "Úsalo para buscar información en la web, consultar documentación, verificar datos, "
        "o investigar temas que requieran fuentes externas. "
        "El resultado es texto plano extraído de la página. "
        "IMPORTANTE: Lee la skill 'obscura-web' antes de usar esta herramienta.",
        {"url": _str("URL completa a visitar (ej: 'https://ejemplo.com/pagina')"),
         "selector": _str("Selector CSS para extraer solo una parte de la página (opcional)"),
         "wait": _str("Tiempo de espera en segundos para páginas dinámicas (default 5)")},
        ["url"]),



    # ── MALDICIÓN (Curse Tool) ────────────────────────────────────────────
    _decl("curse_user",
        "Maldice a un usuario: sus mensajes se borran y reenvían traducidos a idiomas random. "
        "Ponle la maldición, maldícelo. "
        "Sinónimos: maldecir, poner maldición, maldícelo, ponle curse, castígalo con la maldición.",
        {"user_id": _str("ID del usuario a maldecir"),
         "duration": _str("Duración: 10m, 1h, 6h, 1d (default: 1h)"),
         "reason": _str("Razón de la maldición (opcional)")},
        ["user_id"]),

    _decl("uncurse_user",
        "Quita la maldición de un usuario. Desmaldícelo, libéralo del curse. "
        "Sinónimos: desmaldecir, quitar maldición, quítale el curse, libéralo de la maldición.",
        {"user_id": _str("ID del usuario a liberar")},
        ["user_id"]),

    _decl("list_cursed_users",
        "Lista todos los usuarios actualmente maldecidos en el servidor.",
        {}, []),

    # ── LAVADO DE BOCA (Mouth Wash Tool) ──────────────────────────────────
    _decl("wash_mouth",
        "Lávale la boca a un usuario: intercepta sus mensajes y los reescribe a versión "
        "tierna y family-friendly via LLM local. Ponle jabón en la boca. "
        "Sinónimos: lavar la boca, ponle jabón, lávale la boca, wash, ponle el lavado.",
        {"user_id": _str("ID del usuario a lavar la boca"),
         "duration": _str("Duracion: 10m, 1h, 6h, 1d (default: 1h)"),
         "reason": _str("Razon (opcional)")},
        ["user_id"]),

    _decl("unwash_mouth",
        "Quita el lavado de boca de un usuario. Déjalo hablar normal, quítale el jabón. "
        "Sinónimos: quitar lavado, quítale el wash, déjalo hablar normal, quítale el jabón.",
        {"user_id": _str("ID del usuario a liberar")},
        ["user_id"]),

    _decl("list_mouth_washed",
        "Lista todos los usuarios con lavado de boca activo.",
        {}, []),

    # ── MACRO-TOOLS (operaciones compuestas en 1 sola call) ──────────────
    _decl("send_user_content_to_channel",
        "MACRO: Manda la foto/avatar/banner de un usuario a un canal. "
        "Busca al usuario por nombre, obtiene su pfp o banner, y lo envía como embed. "
        "Sinónimos: manda su foto, manda su pfp, manda su avatar, pasa su foto a, envía su avatar.",
        {"user_name": _str("Nombre del usuario a buscar"),
         "channel_name": _str("Nombre del canal destino (parcial OK)"),
         "content_type": _str("Qué enviar: 'avatar' (default) o 'banner'")},
        ["user_name", "channel_name"]),

    _decl("bulk_channel_action",
        "MACRO: Ejecuta una acción en múltiples canales a la vez. "
        "Acciones: 'lock', 'unlock', 'slowmode'. Evita llamar lock_channel N veces.",
        {"channel_ids": _str("IDs de canales separados por coma"),
         "action": _str("Acción: 'lock' | 'unlock' | 'slowmode'"),
         "value": _str("Valor para slowmode (segundos). Ignorado para lock/unlock.")},
        ["channel_ids", "action"]),

    _decl("zzz_build_card",
        "Genera una build card de Zenless Zone Zero para un jugador. "
        "Consulta la API de ZZZ con el UID y devuelve una imagen PNG con stats, discos, weapon y score. "
        "Si no se especifica agente, devuelve la lista de agentes disponibles en el showcase.",
        {"uid": _str("UID numérico del jugador de ZZZ"),
         "agente": _str("Nombre del agente (opcional, case-insensitive). Si no se pone, lista los disponibles.")},
        ["uid"]),

    # ── Knowledge Base (Interactive RAG) ──────────────────────────────────
    _decl("knowledge_search",
        "Busca en la base de conocimiento del servidor. Úsala cuando necesites recordar algo, "
        "buscar información que te hayan enseñado, o consultar datos del server/juego/usuarios. "
        "Es tu MEMORIA PERSISTENTE. Busca por significado, no solo palabras exactas.",
        {"query": _str("Qué buscar (descripción natural de lo que necesitas saber)"),
         "limit": _int("Máximo resultados (default 5, máx 10)")},
        ["query"]),

    _decl("knowledge_store",
        "Guarda información nueva en tu base de conocimiento. Úsala cuando alguien te enseñe algo, "
        "cuando aprendas un dato importante, o cuando quieras recordar algo para el futuro. "
        "La key debe ser descriptiva y única (snake_case).",
        {"key": _str("Identificador único descriptivo (snake_case, ej: 'cumple_leon', 'regla_spoilers')"),
         "content": _str("El contenido/información a guardar (máx 500 chars)"),
         "tags": _str("Tags separados por coma para categorizar (ej: 'usuario,leon,cumpleaños')")},
        ["key", "content"]),

    _decl("knowledge_update",
        "Actualiza una entrada existente en la base de conocimiento. "
        "Usa esto cuando la información cambie o necesite corrección.",
        {"key": _str("Key exacta de la entrada a actualizar"),
         "content": _str("Nuevo contenido (reemplaza el anterior)"),
         "tags": _str("Nuevos tags (opcional, reemplaza los anteriores)")},
        ["key", "content"]),

    _decl("knowledge_delete",
        "Elimina una entrada de la base de conocimiento. "
        "Solo úsala si la información es incorrecta o ya no es relevante.",
        {"key": _str("Key exacta de la entrada a eliminar")},
        ["key"]),

    # ── Birthdays ─────────────────────────────────────────────────────────
    _decl("register_birthday",
        "Registra el cumpleaños de un usuario. Puede registrar 1 o varios. "
        "Si el usuario da su cumpleaños o el de alguien más, usa esta tool. "
        "Necesitas el user_id (búscalo con get_user_by_name si no lo tienes).",
        {"user_id": _str("ID del usuario"),
         "day": _str("Día del mes (1-31)"),
         "month": _str("Mes (1-12)"),
         "name": _str("Nombre/apodo del usuario (para referencia)")},
        ["user_id", "day", "month"]),

    _decl("get_birthdays",
        "Consulta cumpleaños registrados. Sin mes = todos. Con mes = solo ese mes.",
        {"month": _str("Mes a consultar (1-12, opcional — sin mes devuelve todos)")},
        []),

    # ── Shop / Redeemables ────────────────────────────────────────────────
    _decl("shop_create",
        "STAFF ONLY. Crea un nuevo item canjeable en la tienda. "
        "Tipos: 'role' (asigna roles), 'coupon' (envía embed-cupón a Aris). "
        "Para roles: payload debe ser JSON con 'role_ids' (lista de IDs). "
        "Para coupon: payload debe tener 'message' (texto del cupón). "
        "duration_hours: si >0, el rol es temporal y se quita al expirar. "
        "Si el usuario compra de nuevo, el tiempo se ACUMULA (no se reinicia).",
        {"name": _str("Nombre del item"),
         "price": _str("Precio en créditos"),
         "type": _str("Tipo: 'role' o 'coupon'"),
         "description": _str("Descripción para los usuarios"),
         "payload": _str("JSON con datos del reward (role_ids, message, etc)"),
         "stock": _str("Stock disponible (-1 = ilimitado, default -1)"),
         "duration_hours": _str("Duración en horas (0 = permanente, >0 = temporal con stacking)"),
         "category": _str("Categoría del item (ej: 'Roles GM', 'Cupones')")},
        ["name", "price", "type"]),

    _decl("shop_list",
        "Lista los items disponibles en la tienda del servidor. Soporta paginación y filtro por categoría. "
        "Usa 'search' para buscar por nombre (funciona con caracteres especiales/unicode).",
        {"show_all": _str("'true' para ver también inactivos (staff only)"),
         "category": _str("Filtrar por categoría (ej: 'Roles GM')"),
         "search": _str("Buscar por nombre (ej: 'Vivian', 'Miyabi')"),
         "offset": _str("Desde qué item empezar (default 0, para paginación)"),
         "limit": _str("Cuántos items mostrar (default 20, máx 50)")},
        []),

    _decl("shop_redeem",
        "Canjea un item de la tienda para un usuario. Deduce créditos y aplica el reward.",
        {"item_id": _str("ID del item a canjear"),
         "user_id": _str("ID del usuario que canjea")},
        ["item_id", "user_id"]),

    _decl("shop_manage",
        "STAFF ONLY. Gestiona items: toggle (activar/desactivar), delete, update precio/stock/desc.",
        {"item_id": _str("ID del item"),
         "action": _str("Acción: 'toggle', 'delete', 'update'"),
         "fields": _str("Para update: JSON con campos a cambiar (price, stock, description, name)")},
        ["item_id", "action"]),

    _decl("shop_bulk_create",
        "STAFF ONLY. Crea MÚLTIPLES items de golpe a partir de una lista de roles. "
        "Busca roles por nombre parcial y crea un item por cada match. "
        "Ideal para crear muchos canjeables de roles similares de una vez.",
        {"role_query": _str("Texto parcial para buscar roles (ej: 'Grandmaster')"),
         "price": _str("Precio en créditos para TODOS los items"),
         "duration_hours": _str("Duración en horas (0=permanente)"),
         "description": _str("Descripción compartida (opcional)")},
        ["role_query", "price"]),

    _decl("economy_stats",
        "Estadísticas de la economía del servidor: créditos en circulación, "
        "ganados/gastados hoy, top earners, treasury.",
        {}, []),

    # ── Music ─────────────────────────────────────────────────────────────
    _decl("play_music",
        "Reproduce música en el canal de voz del usuario. Busca en YouTube por nombre o URL. "
        "El usuario DEBE estar en un canal de voz. Si piden 'pon música', 'reproduce', 'play', usa esto.",
        {"query": _str("Nombre de la canción, artista, o URL de YouTube"),
         "user_id": _str("ID del usuario que pidió la música (para encontrar su canal de voz)")},
        ["query", "user_id"]),

    _decl("music_queue",
        "Muestra qué se está reproduciendo y la cola de música actual.",
        {}, []),

    # ── Utilidades Adicionales Registradas ──────────────────────────────────
    _decl("get_server_info",
        "Muestra información técnica y estadísticas del servidor de Discord (ID, miembros, canales, roles, boost level).",
        {}, []),

    _decl("translate_message",
        "Traduce un mensaje específico del servidor a un idioma objetivo.",
        {"message_id": _str("ID del mensaje a traducir"),
         "target_language": _str("Idioma de destino (ej: 'inglés', 'japonés')"),
         "channel_id": _str("ID del canal del mensaje (opcional, usa el actual si no se provee)")},
        ["message_id", "target_language"]),

    _decl("summarize_thread",
        "Lee la historia reciente de un hilo de Discord y genera un resumen de la conversación.",
        {"thread_id": _str("ID del hilo a resumir"),
         "limit": _int("Límite máximo de mensajes a leer (default 100, máx 200)")},
        ["thread_id"]),

    _decl("generate_rules",
        "Genera una propuesta completa de reglas y normas del servidor basadas en la estructura de canales y roles.",
        {}, []),

    _decl("smart_search",
        "Búsqueda semántica avanzada en la base de datos del historial de mensajes del servidor.",
        {"query": _str("Texto de búsqueda / consulta semántica"),
         "scope": _str("Alcance de búsqueda: 'all' o ID de canal/usuario (default 'all')"),
         "hours": _int("Buscar mensajes de las últimas N horas (default 72)")},
        ["query"]),

    _decl("sentiment_snapshot",
        "Analiza el sentimiento y tono general de la conversación reciente en el servidor.",
        {"hours": _int("Horas recientes a analizar (default 6)")},
        []),
]

DJINN_TOOL = types.Tool(function_declarations=TOOL_DECLARATIONS)
YOUKAI_TOOL = DJINN_TOOL  # Alias para compatibilidad con código heredado
