# Todoist → Obsidian TaskNotes

[English](README.md) | Русский

Миграция задач из [экспорта Todoist в JSON](https://github.com/darekkay/todoist-export)
в vault Obsidian с плагином
[TaskNotes](https://github.com/callumalpass/tasknotes).

Мигратор записывает задачи через HTTP API TaskNotes, сохраняет ID задач Todoist
в пользовательском поле TaskNotes для идемпотентности и при необходимости создаёт
заметки проектов в vault.

## Возможности

- Преобразует задачи Todoist в задачи TaskNotes.
- Сохраняет заголовки, описания, статус, приоритет, запланированные даты,
  дедлайны, метки, проекты,
  длительность, даты создания, комментарии и связи родитель–потомок.
- Использует `todoist_id` как пользовательское поле, чтобы при повторных
  запусках не создавать дубликаты задач.
- Поддерживает dry-run, ограниченные пробные прогоны, человеко-читаемые отчёты
  и отчёты в JSON.
- Включает модульные тесты для маппинга, разбора CLI, отчётов, dry-run и
  поведения полей `scheduled` / `dateCreated`.

## Требования

- Python 3.10 или новее.
- Obsidian Desktop.
- Плагин TaskNotes с включённым HTTP API.
- Экспорт Todoist в JSON по пути `source-todoist/todoist.json`.

Установка зависимостей Python:

```bash
python -m pip install -r requirements.txt
```

## Настройка TaskNotes

Запустите Obsidian, откройте целевой vault и включите HTTP API TaskNotes:

```text
Settings -> TaskNotes -> Integrations -> HTTP API
```

На том же экране настроек укажите в поле **API authentication token**
произвольную строку (например, `token`). То же значение передайте в
`--api-token` при запуске скрипта миграции.

## Использование

Миграция:

```bash
python migrate_todoist_to_tasknotes.py --api-token=<token>
```

Успешный повторный прогон не должен создавать новых задач и должен помечать
дубликаты как пропущенные.

## Параметры

```text
--json-path=<path>           Путь к JSON-экспорту Todoist.
--api-base=<url>             Базовый URL API TaskNotes (по умолчанию: http://127.0.0.1:8080).
--api-token=<token>          Токен API TaskNotes (обязателен).
--vault-root=<path>          Корень vault Obsidian для заметок проектов.
--dry-run                    Печатать payload-ы без вызова API.
--limit=<n>                  Создать не более N новых задач.
--include-deleted            Включить удалённые элементы Todoist.
--include-completed          Включить завершённые элементы Todoist.
--no-include-completed       Исключить завершённые элементы Todoist.
--stop-on-error              Остановиться после первой неудачной попытки создания задачи.
--report-format=<format>     Формат отчёта: human или json.
```

## Сводка маппинга

| Todoist | TaskNotes |
| --- | --- |
| `content` | `title` |
| `description` | `details` |
| `checked` | `status` |
| `priority` | `priority` |
| `due.date` / `due.datetime` | `scheduled` |
| `deadline.date` | `due` |
| `labels[]` | `tags[]` |
| `project.name` | `projects[]` |
| `duration` | `timeEstimate` |
| `id` | `customProperties.todoist_id` |
| `added_at` | `dateCreated` |
| `parent_id` | Wiki-ссылка на родителя в `projects[]` |
| `notes[]` | Секция `## Todoist notes` в `details` |

Миграция намеренно **не** переносит секции, метки времени
обновления, ID пользователей, audit-флаги и повторяемость Todoist как нативную
повторяемость TaskNotes.

## Подзадачи

Подзадачи обрабатываются в два прохода. В первом проходе задачи создаются в
порядке, в котором они встречаются в экспорте Todoist. Во втором проходе
пересобирается кэш `todoist_id` и добавляются недостающие wiki-ссылки на
родителя для подзадач, чей родитель был создан позже в первом проходе.

`--limit` применяется только к созданию новых задач в первом проходе. При
dry-run второй проход пропускается.

## Тестирование

Запуск стандартного набора тестов:

```bash
pytest
```

Интеграционные тесты, требующие запущенного API TaskNotes, по умолчанию
исключены. Чтобы запустить их явно:

```bash
pytest -m integration
```

## Структура проекта

```text
migrate_todoist_to_tasknotes.py     CLI полной миграции.
scripts/
  todoist_tasknotes_mapping.py      Маппинг и вспомогательные функции API TaskNotes.
  todoist_projects.py               Заметки проектов и wiki-ссылки.
tests/                              Модульные и интеграционные тесты.
documentation/
  GPT_info.md                       Справочные заметки по миграции.
  HTTP_API.md                       Справочник HTTP API TaskNotes.
```

## Примечания

- Скрипты создают и обновляют задачи только через HTTP API TaskNotes.
- Файлы заметок проектов создаются напрямую в корне vault, если их ещё нет.
- Obsidian должен быть запущен, пока миграция использует HTTP API.
- Если API возвращает `401`, проверьте настроенный токен API.
