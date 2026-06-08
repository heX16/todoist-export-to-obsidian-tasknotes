# Todoist to Obsidian TaskNotes

Migrate tasks from a [Todoist JSON export](https://github.com/darekkay/todoist-export)
into an Obsidian vault that uses the
[TaskNotes](https://github.com/callumalpass/tasknotes) plugin.

The migration writes tasks through the TaskNotes HTTP API, keeps Todoist task IDs
in a custom TaskNotes field for idempotency, and creates project notes in the
vault when needed.

## Features

- Converts Todoist tasks into TaskNotes tasks.
- Preserves titles, descriptions, status, priority, due dates, labels, projects,
  durations, creation dates, comments, and parent-child task links.
- Uses `todoist_id` as a custom field to avoid duplicate task creation on
  repeated runs.
- Supports dry runs, limited trial runs, human-readable reports, and JSON
  reports.
- Includes unit tests for mapping, CLI parsing, reporting, dry runs, and
  scheduled/date-created behavior.

## Requirements

- Python 3.10 or newer.
- Obsidian Desktop.
- The TaskNotes plugin with its HTTP API enabled.
- A Todoist JSON export at `source-todoist/todoist.json`.

Install Python dependencies:

```bash
python -m pip install -r requirements.txt
```

## TaskNotes Setup

Start Obsidian, open the target vault, and enable the TaskNotes HTTP API:

```text
Settings -> TaskNotes -> Integrations -> HTTP API
```

The vault must define a TaskNotes user field for idempotency:

- Key: `todoist_id`
- Type: `text`

After changing TaskNotes user fields, reload the plugin or restart Obsidian.

## Usage

Run a dry run first to inspect the payloads without writing anything:

```bash
python scripts/migrate_todoist_to_tasknotes.py --api-token=<token> --dry-run --limit 5
```

Run a small real migration:

```bash
python scripts/migrate_todoist_to_tasknotes.py --api-token=<token> --limit 10
```

Run the full migration:

```bash
python scripts/migrate_todoist_to_tasknotes.py --api-token=<token>
```

Run the migration again to verify idempotency. A successful repeat run should
create no new tasks and report duplicates as skipped.

## Options

```text
--json-path=<path>           Path to the Todoist JSON export.
--api-base=<url>             TaskNotes API base URL (default: http://127.0.0.1:8080).
--api-token=<token>          TaskNotes API token (required).
--vault-root=<path>          Obsidian vault root used for project notes.
--dry-run                    Print payloads without calling the API.
--limit=<n>                  Create at most N new tasks.
--include-deleted            Include deleted Todoist items.
--include-completed          Include completed Todoist items.
--no-include-completed       Exclude completed Todoist items.
--stop-on-error              Stop after the first failed task creation.
--report-format=<format>     Report format: human or json.
```

## Mapping Summary

| Todoist | TaskNotes |
| --- | --- |
| `content` | `title` |
| `description` | `details` |
| `checked` | `status` |
| `priority` | `priority` |
| `due.date` | `due` |
| `labels[]` | `tags[]` |
| `project.name` | `projects[]` |
| `duration` | `timeEstimate` |
| `id` | `customProperties.todoist_id` |
| `added_at` | `dateCreated` |
| `parent_id` | Parent wiki-link in `projects[]` |
| `notes[]` | `## Todoist notes` section in `details` |

The migration intentionally does not preserve Todoist deadlines, sections,
update timestamps, user IDs, audit flags, or Todoist recurrence as native
TaskNotes recurrence.

## Subtasks

Subtasks are handled in two passes. The first pass creates tasks in the order
found in the Todoist export. The second pass rebuilds the `todoist_id` cache and
adds missing parent wiki-links for subtasks whose parent task was created later
in the first pass.

`--limit` applies only to new task creation in the first pass. Dry runs skip the
second pass.

## Testing

Run the default test suite:

```bash
pytest
```

Integration tests that require a running TaskNotes API are excluded by default.
To run them explicitly:

```bash
pytest -m integration
```

## Project Structure

```text
scripts/
  migrate_todoist_to_tasknotes.py   Full migration CLI.
  todoist_tasknotes_mapping.py      Mapping and TaskNotes API helpers.
  todoist_projects.py               Project note and wiki-link helpers.
tests/                              Unit and integration tests.
documentation/
  GPT_info.md                       Migration reference notes.
  HTTP_API.md                       TaskNotes HTTP API reference.
```

## Notes

- The scripts create and update tasks only through the TaskNotes HTTP API.
- Project note files are created directly in the vault root when missing.
- Obsidian must be running while the migration uses the HTTP API.
- If the API returns `401`, check the configured API token.
