"""
utils.tools — paquete previsto para la migración del god object
`utils/discord_tools.py` (Wave 8, F3.1).

**Estado actual: SCAFFOLD VACÍO.** No hay handlers migrados todavía. Toda la
lógica sigue en `utils/discord_tools.py`. Este `__init__.py` existe para que
las migraciones futuras puedan ir reemplazando módulo por módulo sin romper
imports externos.

Plan de migración (1 PR por categoría):

  Categoría             →  Módulo destino
  ─────────────────────────────────────────
  Moderación destructiva →  utils/tools/moderation.py
                           (ban_user, kick_user, mute_user, purge_messages,
                            mass_timeout, warn_user, seal_user)
  Canales               →  utils/tools/channels.py
                           (create_channel, delete_channel, set_topic,
                            move_member, set_slowmode, edit_channel)
  Roles                 →  utils/tools/roles.py
                           (add_role, remove_role, create_role, delete_role,
                            bulk_assign_role_all, bulk_remove_role_all)
  Información           →  utils/tools/info.py
                           (get_user_info, get_server_info,
                            get_channel_info, get_audit_log)
  Web / browsing        →  utils/tools/web.py
                           (web_fetch, fetch_url_preview, weather)
  Scheduling            →  utils/tools/scheduling.py
                           (schedule_message, cancel_scheduled, broadcast)
  Admin / backup        →  utils/tools/admin.py
                           (backup_server, audit_log, dashboard_record)
  Análisis social       →  utils/tools/analytics.py
                           (analyze_social_graph, find_communities,
                            detect_coordinated_activity)

Patrón de migración (cada PR):
  1. Crear utils/tools/<categoria>.py con los handlers + sus declaraciones
     (`_decl(...)`).
  2. Crear utils/tools/<categoria>_test.py con tests unitarios cubriendo
     dispatch + happy path de cada tool.
  3. En utils/discord_tools.py, reemplazar las definiciones por
     `from utils.tools.<categoria> import _do_<tool>` (re-export shim).
  4. Verificar runtime: cargar bot en staging, probar 1-2 tools de la
     categoría migrada.
  5. Si OK → mergear. Si no → revertir solo ese PR.

Prerequisito DURO: tests del dispatcher (`ToolExecutor._dispatch`) en verde.
Sin eso, no se garantiza que el shim pase los argumentos correctamente.

Ver `.code-review/05-plan.md` (F3.1) para detalles.
"""

# Por ahora vacío: los handlers siguen en utils/discord_tools.py.
__all__: list[str] = []
