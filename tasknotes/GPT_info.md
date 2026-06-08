# Todoist → TaskNotes migration reference

Справочник по миграции задач из Todoist JSON export в Obsidian TaskNotes через HTTP API.

## Правила

- Исходный экспорт: `source-todoist/todoist.json`
- Целевой vault (только чтение для проверки): `target-obsidian`
- Создавать и обновлять задачи **только через TaskNotes HTTP API**, не писать task-markdown в vault вручную
- Исключение: при миграции **создаются project notes** напрямую в корне vault (файл `<Project>.md`), если его ещё нет
- После API-записи сверять результат: исходный JSON ↔ ответ API ↔ markdown-файл
- Не запускать справочные репозитории в `documentation/` — только читать
- Python: `python3`, комментарии и commit messages на английском, строки в одинарных кавычках

## Связанные репозитории (справочные)

- [`darekkay/todoist-export`](https://github.com/darekkay/todoist-export)
- [`singofwalls/Todoist-to-Markdown`](https://github.com/singofwalls/Todoist-to-Markdown)

## Скрипты

| Скрипт | Назначение |
|---|---|
| `scripts/todoist_tasknotes_mapping.py` | Общий маппинг, HTTP-клиент, идемпотентность |
| `scripts/migrate_todoist_to_tasknotes.py` | Полная миграция |
| `migrate_full.sh` | Полный прогон миграции (обёртка) |

```bash
python3 scripts/migrate_todoist_to_tasknotes.py --dry-run --limit 5
python3 scripts/migrate_todoist_to_tasknotes.py --limit 10
python3 scripts/migrate_todoist_to_tasknotes.py
```

Итоговый отчёт каждого прогона печатается в stdout (человеко-читаемый формат по умолчанию, либо JSON).

## Запуск миграции (коротко)

### Что нужно перед стартом

- Obsidian Desktop запущен, плагин TaskNotes включён
- Включён TaskNotes HTTP API: `Settings -> TaskNotes -> Integrations -> HTTP API`
- Экспорт Todoist есть: `source-todoist/todoist.json`
- Для идемпотентности настроен user field `todoist_id` (см. ниже)

### Рекомендуемый порядок запуска

1. Dry-run (проверить payload-ы без записи):

```bash
python3 scripts/migrate_todoist_to_tasknotes.py --dry-run --limit 5
```

2. Пробный реальный запуск (создать 10 новых задач):

```bash
python3 scripts/migrate_todoist_to_tasknotes.py --limit 10
```

3. Полный прогон:

```bash
python3 scripts/migrate_todoist_to_tasknotes.py
```

4. Идемпотентность (повторный прогон должен дать `created: 0`, всё уйдёт в `skipped_duplicate`):

```bash
python3 scripts/migrate_todoist_to_tasknotes.py
```

### Проекты (Project notes)

- Корневые задачи получают `projects: [<Todoist project name>]`.
- Сабтаски получают в `projects` только wiki-link на родителя (без ссылки на проект).
- При реальном запуске мигратор **создаёт** в корне vault файл `<Project>.md`, если его ещё нет.
- Vault root можно задать через `--vault-root` (по умолчанию `target-obsidian/`).

### Если что-то сломалось (минимум)

- API не отвечает: проверь `GET /api/health` и что Obsidian запущен.
- `401`: проверь `--api-token` и что токен совпадает с настройками плагина.

## TaskNotes HTTP API

- Base URL: `http://127.0.0.1:16876`
- Token: `tasknotes-token`
- Заголовок: `Authorization: Bearer tasknotes-token`
- Документация: [`HTTP_API.md`](HTTP_API.md)

Полезные endpoints:

- `GET /api/health`
- `GET /api/tasks` — только пагинация (`limit`, `offset`); фильтры → HTTP 400
- `POST /api/tasks`
- `GET /api/tasks/:id` — `:id` = URL-encoded path задачи
- `PUT /api/tasks/:id`
- `POST /api/tasks/query` — расширенная фильтрация

`POST /api/tasks` требует `title`. Частые поля: `details`, `status`, `priority`, `due`, `scheduled`, `tags`, `contexts`, `projects`, `timeEstimate`, `recurrence`, `blockedBy`, `customProperties`.

Enum-значения `status` и `priority` сверять с текущим vault/API, не угадывать.

### Кастомное поле `todoist_id`

Для идемпотентности в vault должен быть настроен user field:

- key: `todoist_id`
- type: `text`
- конфиг: `target-obsidian/.obsidian/plugins/tasknotes/data.json` → `userFields`

После изменения user fields перезагрузить TaskNotes (disable/enable plugin или restart Obsidian).

При создании задачи скрипт передаёт:

```json
{
  "todoist_id": "6c2pWG4XgMCXPhM8",
  "customProperties": { "todoist_id": "6c2pWG4XgMCXPhM8" }
}
```

В markdown это попадает в frontmatter:

```yaml
todoist_id: 6c2pWG4XgMCXPhM8
```

## Маппинг Todoist → TaskNotes (текущий)

| Todoist | TaskNotes | Примечание |
|---|---|---|
| `content` | `title` | без искажений |
| `description` | `details` | только текст описания |
| `checked` | `status` | `false→open`, `true→done` |
| `priority` | `priority` | `1→none`, `2→low`, `3→normal`, `4→high` |
| `due.date` | `due` | ISO date |
| `labels[]` | `tags[]` | TaskNotes добавляет `task` |
| `project.name` | `projects[]` | только у корневых задач (без `parent_id`); имя, не id |
| `duration` | `timeEstimate` | минуты (minute/hour/day) |
| `id` | `customProperties.todoist_id` | идемпотентность |
| `added_at` | `dateCreated` | ISO datetime, дата создания задачи |
| `parent_id` | `projects[]` wiki-link на родителя | только parent link, без project link |
| `notes[]` | `details` | секция `## Todoist notes`, если есть |

**Не переносится** (осознанно):

- `deadline`, `section`, `updated_at`, user uids, audit flags — не сохраняются отдельно
- `scheduled`, `dateModified` — выставляет TaskNotes
- `recurrence` из Todoist `due` — не маппится в native `recurrence`

**Не добавляется** блок `## Todoist migration metadata` в `details`.

### Subtasks

- Корень → `projects: [TodoistProject]`
- Сабтаск → только `projects: ["[[parent-basename]]"]` (stem файла родителя в vault)

**Два прохода:** parent link требует путь к файлу родителя, а в экспорте дети часто идут раньше родителей — сортировка не нужна.

1. **Pass 1** (`POST`): создать задачи в порядке JSON. Сабтаск с известным родителем — сразу с link, иначе без `projects`.
2. **Pass 2** (`GET`+`PUT`, только реальный запуск): пересобрать кэш `todoist_id→path`, дописать недостающий `[[parent]]` в `projects` (append-only, идемпотентно).

`--limit` — только pass 1. `--dry-run` — pass 2 пропускается.

### Идемпотентность

Перед `POST`:

1. `GET /api/tasks` (paginate) → список путей
2. для каждого пути `GET /api/tasks/:id` → читать `customProperties.todoist_id`
3. если `todoist_id` уже есть → `SKIP duplicate`, без `POST`

Повторный полный прогон после успешной миграции: `created: 0`, все задачи `skipped_duplicate`.

`--limit N` считает только **созданные** задачи; пропущенные дубликаты лимит не уменьшают.

## Структура `source-todoist/todoist.json`

Экспорт через Todoist Sync API (`resource_types: ["all"]`).

### Основные коллекции

| Ключ | Размер | Назначение |
|---|---:|---|
| `items` | 334 | задачи |
| `projects` | 11 | проекты |
| `sections` | 6 | секции |
| `labels` | 30 | теги |
| `collaborators` | 2 | пользователи |
| `notes` | 0 | комментарии к задачам |
| `project_notes` | 0 | заметки к проектам |
| `reminders` | 0 | напоминания |
| `completed_info` | 21 | агрегаты завершённых (не список задач) |

### `items` — ключевые поля

- `id`, `content`, `description`, `checked`, `completed_at`
- `project_id`, `section_id`, `parent_id`
- `labels[]`, `priority` (1–4), `due`, `deadline`, `duration`
- `added_at`, `updated_at`, user uid fields
- `is_deleted`, `is_collapsed`, `child_order`, `postponed_count`

Связи: `project_id` → `projects`, `section_id` → `sections`, `parent_id` → другой `item`, `labels` → `labels`, notes → `notes[].item_id`.

### Статистика экспорта

| Метрика | Значение |
|---|---:|
| Всего `items` | 334 |
| `is_deleted: true` | 0 |
| `checked: true` | 0 |
| С `parent_id` | 152 |
| С `section_id` | 17 |
| С `due` | 22 |
| С `deadline` | 1 |
| С `description` | 120 |
| С `labels` | 93 |

## TaskNotes: поля задачи

### Ответ `GET /api/tasks/:id`

- `path`, `title`, `status`, `priority`, `due`, `scheduled`
- `tags`, `contexts`, `projects`, `details`
- `dateCreated`, `dateModified`, `archived`
- `customProperties` — user fields, включая `todoist_id`

### Пример frontmatter после миграции

```yaml
title: Взять все что тут написано, и составить расписание
status: open
priority: none
scheduled: 2026-06-08
projects:
  - Routines
tags:
  - task
todoist_id: 6c2pWG4XgMCXPhM8
```

Body (`details`): только описание из Todoist (и `## Todoist notes`, если были комментарии).

## Defaults мигратора

| Параметр | Default |
|---|---|
| `--json-path` | `source-todoist/todoist.json` |
| `--api-base` | `http://127.0.0.1:16876` |
| `--api-token` | `tasknotes-token` |
| `--vault-root` | `target-obsidian` (создание `<Project>.md` в корне vault) |
| `--include-deleted` | skip с логом |
| `--include-completed` | include (`status: done`) |
| `--report-format` | `human` (печать отчёта в stdout; варианты: `human`, `json`) |

## Подводные камни

1. **`:id` в URL** — URL-encoded path: `urllib.parse.quote(path, safe='')`
2. **TaskNotes добавляет тег `task`** — это нормально
3. **`dateCreated`** — переносится из Todoist `added_at`; **`dateModified` / `scheduled`** — выставляет TaskNotes
4. **Labels** — в экспорте строковые имена; код поддерживает и id через `resolve_label_names()`
5. **Obsidian должен быть запущен** — API работает только с desktop Obsidian + TaskNotes HTTP API
6. **Без `userFields.todoist_id`** API не сохранит кастомное поле → идемпотентность сломается
7. **Не путать `--limit`** с «повторить те же N задач» — он создаёт N новых после skip

## Карта документов

```
GPT_info.md           — этот справочник
HTTP_API.md           — документация TaskNotes API
```

## Статус проекта

| Компонент | Статус |
|---|---|
| Маппинг + API-модуль | Готово |
| Скрипт полной миграции | Готово, протестирован (`--dry-run`, `--limit 3`, идемпотентность) |
| Runbook | Готово |
| Полная миграция 334 задач | **Не выполнена** |

Следующий шаг: полный прогон миграции.
