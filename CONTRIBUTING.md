# Contributing — Workflow de git para Fairy / Youkai

> Desde 2026-05-16 este proyecto se versiona con git. Este documento explica
> cómo trabajamos con commits, qué se versiona y qué no, y la convención de
> mensajes que usamos.

---

## Filosofía

- **Cada cambio significativo es un commit.** Evitamos commits gigantes que
  mezclan varios temas — cuesta más revertir, más leer, más entender.
- **El working tree siempre debe estar funcionando.** Si los tests fallan o
  los cogs no importan, no committeamos hasta arreglarlo.
- **Mensajes descriptivos en español o inglés**, ambos aceptados, con
  estructura **Conventional Commits** para que el changelog se pueda generar
  automáticamente y el historial sea legible.

---

## Convención de mensajes (Conventional Commits)

Formato:

```
<tipo>(<ámbito opcional>): <descripción corta en imperativo>

<cuerpo opcional explicando el por qué, no el qué>

<footer opcional con BREAKING CHANGE: o issue references>
```

### Tipos

| Tipo | Cuándo usarlo |
|---|---|
| `feat` | Funcionalidad nueva visible al usuario o LLM (tool nueva, slash command nuevo, sistema nuevo) |
| `fix` | Bug fix |
| `refactor` | Reestructuración sin cambio de comportamiento (mover código, renombrar) |
| `docs` | Solo documentación (README, CHANGELOG, comentarios) |
| `style` | Cambio cosmético (formato, imports, sin lógica) |
| `test` | Añadir o ajustar tests |
| `chore` | Tareas de mantenimiento sin impacto funcional (deps, .gitignore, configs) |
| `perf` | Mejora de performance |
| `ci` | Cambios en `.github/workflows/` |

### Ámbitos comunes en este proyecto

`tools` · `treasury` · `loans` · `automod` · `nlp` · `db` · `kadath` · `logs` ·
`security` · `routing` · `discord_tools` · `orchestrator` · `embeddings` ·
`api` · `tests` · `docs`

### Ejemplos buenos (sacados del historial real)

```
feat(treasury): banco bidireccional con bootstrap 6000 cr
fix: token leak en logs + bugs latentes detectados por análisis estático
refactor(tools): mover TOOL_DECLARATIONS a utils/tools/_declarations.py
docs: README + CHANGELOG + deprecated/README + mover dead code
style(discord_tools): consolidar imports + docstring del módulo
```

### Ejemplos malos

```
update              ← ¿qué? ¿por qué?
fix bug             ← ¿qué bug?
WIP                 ← no committear WIP en main
asdf                ← no
```

---

## Qué NO se versiona (ya cubierto por `.gitignore`)

### Secretos
- `.env` — token de Discord, API keys
- Cualquier archivo con `token`, `secret`, `credential` en el nombre

### Datos de usuarios
- `db/` (toda la carpeta — patrón amplio defensivo)
- `data/personas/` — skills personalizadas por usuario
- `data/kadath_saves/` — saves de jugadores
- `data/banned_media.bin` y `.json` — hashes de medios baneados
- `data/dashboard.json`

### Pesados / regenerables
- `models/`, `*.gguf`, `*.onnx`, `*.onnx.data` — modelos descargables
- `logs/` — logs rotativos diarios
- `venv/`, `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`

### Backups / históricos pesados
- `deprecated/data_backups/`
- `deprecated/kadath_v1_backup_*/saves_v1/`

### IDE
- `.vscode/`, `.idea/`, `*.swp`, `.DS_Store`

> ⚠ **Antes de un commit**, mirá `git status` y verificá que no se cuele algo
> sensible. Si algo aparece raro, agregalo al `.gitignore` antes de committear.

---

## Comandos básicos del día a día

### Ver qué cambió

```bash
git status                    # archivos modificados/nuevos
git diff                      # diff de cambios sin staged
git diff --cached             # diff de lo staged (listo para commit)
git diff archivo.py           # diff de un archivo específico
git log --oneline             # historial corto
git log --oneline -10         # últimos 10 commits
git log archivo.py            # historial de un archivo
git show <hash>               # ver qué hizo un commit específico
```

### Hacer un commit

```bash
git add archivo.py            # stagear un archivo
git add cogs/treasury.py utils/database.py   # múltiples archivos
git add -p                    # stagear interactivamente (recomendado para commits limpios)
git commit -m "feat(treasury): añadir comando /banco transferir"
```

> **Evitá `git add .` o `git add -A`** salvo que estés seguro de que todo lo
> modificado debe ir junto. Es la forma típica de committear archivos sin querer.

### Revertir cosas

```bash
# Restaurar un archivo a como estaba en el último commit (descarta cambios locales)
git checkout HEAD -- archivo.py

# Restaurar a un commit anterior específico (sin perder los siguientes)
git revert <hash>             # crea un commit nuevo que deshace ese

# Volver el working tree completo a un commit anterior (DESTRUCTIVO)
git reset --hard <hash>       # ⚠ pierde todo lo posterior, usar con cuidado
```

### Ver qué cambió entre dos puntos

```bash
git diff HEAD~3 HEAD          # qué cambió en los últimos 3 commits
git diff main feature-branch  # qué cambió entre dos ramas
```

### Branches (para experimentar sin romper main)

```bash
git checkout -b probando-x    # crear y cambiar a rama nueva
git checkout main             # volver a main
git branch                    # listar ramas
git branch -d probando-x      # borrar rama (si fue mergeada)
git merge probando-x          # mergear rama actual con probando-x
```

---

## Flujo de trabajo del día

```
1. Edito código
2. ./venv/bin/python -m pytest tests/    ← verifico que no rompí nada
3. git status                            ← reviso qué cambió
4. git diff                              ← reviso el diff
5. git add archivos_relevantes
6. git commit -m "tipo(ámbito): mensaje"
7. (continuar con otro cambio)
```

---

## Cuando trabajamos con asistentes (Kiro, Claude Code, Codex, Cursor)

A partir de 2026-05-16 los asistentes pueden hacer commits **cuando se les
pida explícitamente o cuando el usuario haya autorizado el modo de trabajo
con commits para la sesión**. Reglas:

1. **Un commit por cambio coherente** — no mezclar refactor con bugfix con
   feature en el mismo commit.
2. **Verificar antes de committear** — `pytest`, importar todos los cogs,
   compile-check.
3. **Usar `git mv`** cuando se mueven archivos para preservar el historial.
4. **Nunca `git push`, `git reset --hard`, `git rebase`, `git clean -f` sin
   permiso explícito**. Estos comandos son destructivos.
5. **Nunca hacer `git push --force`** bajo ninguna circunstancia.
6. **Nunca tocar `git config` global**.
7. **Si algo no compila o tests fallan**, no committear hasta arreglarlo.

---

## Política de ramas

Por ahora trabajamos directamente en `main` (proyecto chico, sin equipo
distribuido). Si en el futuro hay multi-developer o multi-asistente:

- `main` → siempre estable
- Features grandes → branch `feat/nombre`, mergear con merge commit cuando esté listo
- Hotfixes → branch `fix/nombre`, mergear inmediatamente

---

## Cómo generar un changelog

`CHANGELOG.md` se mantiene a mano por ahora. Para regenerar desde commits:

```bash
git log --oneline --since='2026-05-15' --pretty=format:'- %s' > /tmp/log.txt
```

Después se agrupa por tipo (feat/fix/refactor/docs) y se redacta.

---

## Recuperación de errores comunes

### "Committeé un archivo sensible (token, .env, db)"
```bash
# Si NO se hizo push aún:
git rm --cached archivo_sensible
echo "archivo_sensible" >> .gitignore
git commit -m "chore: untrack <archivo>, añadir a .gitignore"

# Si ya se hizo push (en este proyecto: no hay remote, así que no aplica),
# hay que reescribir historial con git-filter-repo y FORZAR PUSH. Pedir ayuda.
```

### "Hice un commit con mensaje malo"
```bash
git commit --amend -m "nuevo mensaje"   # solo si NO hiciste push
```

### "Quiero deshacer el último commit pero conservar los cambios"
```bash
git reset --soft HEAD~1   # los archivos quedan staged, podés re-committear
```

### "Borré un archivo sin querer"
```bash
git checkout HEAD -- archivo_borrado.py
```

---

## Recursos

- [Conventional Commits spec](https://www.conventionalcommits.org/)
- [Pro Git book](https://git-scm.com/book/en/v2) (gratis online)
- `git help <comando>` — manual local
