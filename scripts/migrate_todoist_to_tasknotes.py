#!/usr/bin/env python3
"""Migrate Todoist JSON export into TaskNotes via HTTP API."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from docopt import docopt

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from todoist_projects import ensure_project_note_exists  # noqa: E402
from todoist_tasknotes_mapping import (  # noqa: E402
    DEFAULT_API_BASE,
    DEFAULT_API_TOKEN,
    DEFAULT_JSON_PATH,
    SubtasksMode,
    api_request,
    build_indexes,
    build_payload,
    build_todoist_id_cache,
    compute_creation_order,
    load_json,
)


DEFAULT_REPORT_PATH = Path('migration_run_report.md')

DEFAULT_VAULT_ROOT = Path(__file__).resolve().parent.parent / 'target-obsidian'

USAGE = f'''Migrate Todoist JSON export into TaskNotes via HTTP API.

Usage:
  migrate_todoist_to_tasknotes.py [options]
  migrate_todoist_to_tasknotes.py (-h | --help)

Options:
  -h --help                           Show this help.
  --json-path=<path>                  Path to Todoist JSON export.
                                      [default: {DEFAULT_JSON_PATH}]
  --api-base=<url>                    TaskNotes API base URL.
                                      [default: {DEFAULT_API_BASE}]
  --api-token=<token>                 TaskNotes API token.
                                      [default: {DEFAULT_API_TOKEN}]
  --vault-root=<path>                 Obsidian vault root directory (for creating project notes directly).
                                      [default: {DEFAULT_VAULT_ROOT}]
  --dry-run                           Do not call API; print would-be payloads.
  --limit=<n>                         Process at most N tasks (parents-first).
  --include-deleted                   Include deleted Todoist items.
  --include-completed                 Include completed Todoist items (default).
  --no-include-completed              Exclude completed Todoist items.
  --stop-on-error                     Stop at first failed task creation.
  --subtasks-mode=<mode>              Subtasks handling mode.
                                      One of: native-project-link, metadata-only, parent-project-only
                                      [default: native-project-link]
  --report=<path>                     Write a markdown report to this path.
                                      [default: {DEFAULT_REPORT_PATH}]
'''


@dataclass
class MigrationStats:
    total: int = 0
    skipped_deleted: int = 0
    skipped_completed: int = 0
    skipped_duplicate: int = 0
    created: int = 0
    failed: int = 0
    created_items: list[dict[str, str]] = field(default_factory=list)
    skipped_duplicate_items: list[dict[str, str]] = field(default_factory=list)
    failed_items: list[dict[str, str]] = field(default_factory=list)


Args = dict[str, Any]


ALLOWED_SUBTASKS_MODES: set[str] = {
    'native-project-link',
    'metadata-only',
    'parent-project-only',
}


def _parse_int(value: str | None, *, option_name: str) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise SystemExit(f'ERROR: {option_name} must be an integer, got {value!r}') from exc


def parse_args(argv: list[str] | None = None) -> Args:
    options = docopt(USAGE, argv=argv)

    limit = _parse_int(options['--limit'], option_name='--limit')
    subtasks_mode = str(options['--subtasks-mode'])
    if subtasks_mode not in ALLOWED_SUBTASKS_MODES:
        allowed = ', '.join(sorted(ALLOWED_SUBTASKS_MODES))
        raise SystemExit(f'ERROR: --subtasks-mode must be one of: {allowed}')

    return {
        'json_path': Path(options['--json-path']),
        'api_base': str(options['--api-base']),
        'api_token': str(options['--api-token']),
        'vault_root': Path(options['--vault-root']),
        'dry_run': bool(options['--dry-run']),
        'limit': limit,
        'include_deleted': bool(options['--include-deleted']),
        'include_completed': not bool(options['--no-include-completed']),
        'stop_on_error': bool(options['--stop-on-error']),
        'subtasks_mode': cast(SubtasksMode, subtasks_mode),
        'report': Path(options['--report']),
    }


def should_skip_item(
    item: dict[str, Any],
    *,
    include_deleted: bool,
    include_completed: bool,
) -> str | None:
    if item.get('is_deleted') and not include_deleted:
        return 'deleted'
    if item.get('checked') and not include_completed:
        return 'completed'
    return None


def create_task(
    api_base: str,
    api_token: str,
    payload: dict[str, Any],
) -> tuple[bool, str, dict[str, Any]]:
    status, body = api_request('POST', f'{api_base}/api/tasks', api_token, payload)
    if status == 201 and body.get('success'):
        task_path = body.get('data', {}).get('path') or body.get('data', {}).get('id') or ''
        return True, task_path, body

    error_message = body.get('error') or json.dumps(body, ensure_ascii=False)
    return False, error_message, body


def write_report(
    report_path: Path,
    *,
    started_at: datetime,
    finished_at: datetime,
    stats: MigrationStats,
    dry_run: bool,
    limit: int | None,
    subtasks_mode: SubtasksMode,
    json_path: Path,
    api_base: str,
) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    partial = limit is not None

    lines = [
        '# Todoist -> TaskNotes migration run report',
        '',
        f'- Started: {started_at.isoformat()}',
        f'- Finished: {finished_at.isoformat()}',
        f'- Dry run: {dry_run}',
        f'- Partial run: {partial}',
        f'- Limit: {limit if limit is not None else "none"}',
        f'- JSON source: `{json_path}`',
        f'- API base: `{api_base}`',
        f'- Subtasks mode: `{subtasks_mode}`',
        '',
        '## Summary',
        '',
        f'- total: {stats.total}',
        f'- skipped_deleted: {stats.skipped_deleted}',
        f'- skipped_completed: {stats.skipped_completed}',
        f'- skipped_duplicate: {stats.skipped_duplicate}',
        f'- created: {stats.created}',
        f'- failed: {stats.failed}',
        '',
    ]

    if stats.created_items:
        lines.extend(['## Created tasks', ''])
        for entry in stats.created_items:
            lines.append(f'- `{entry["todoist_id"]}` -> `{entry["task_path"]}` ({entry["title"]})')
        lines.append('')

    if stats.skipped_duplicate_items:
        lines.extend(['## Skipped duplicates', ''])
        for entry in stats.skipped_duplicate_items:
            lines.append(f'- `{entry["todoist_id"]}` already at `{entry["task_path"]}`')
        lines.append('')

    if stats.failed_items:
        lines.extend(['## Failed tasks', ''])
        for entry in stats.failed_items:
            lines.append(f'- `{entry["todoist_id"]}`: {entry["error"]}')
        lines.append('')

    report_path.write_text('\n'.join(lines), encoding='utf-8')


def migrate(args: Args) -> int:
    started_at = datetime.now(timezone.utc)
    data = load_json(args['json_path'])
    indexes = build_indexes(data)
    items = list(indexes['items'].values())
    ordered_items = compute_creation_order(items)

    stats = MigrationStats(total=len(ordered_items))
    todoist_id_cache: dict[str, str] = {}
    created_paths: dict[str, str] = {}

    if not args['dry_run']:
        health_status, health_body = api_request('GET', f'{args["api_base"]}/api/health', args["api_token"])
        if health_status != 200 or not health_body.get('success'):
            print('ERROR: TaskNotes API health check failed.', file=sys.stderr)
            print(json.dumps(health_body, indent=2, ensure_ascii=False), file=sys.stderr)
            return 1

        print('Building todoist_id cache from existing TaskNotes tasks...')
        todoist_id_cache = build_todoist_id_cache(args['api_base'], args['api_token'])
        print(f'Found {len(todoist_id_cache)} previously imported tasks.')

    processed = 0
    for item in ordered_items:
        if args['limit'] is not None and processed >= args['limit']:
            break

        todoist_id = item['id']
        skip_reason = should_skip_item(
            item,
            include_deleted=args['include_deleted'],
            include_completed=args['include_completed'],
        )
        if skip_reason == 'deleted':
            stats.skipped_deleted += 1
            print(f'SKIP deleted: {todoist_id} ({item.get("content", "")})')
            continue
        if skip_reason == 'completed':
            stats.skipped_completed += 1
            print(f'SKIP completed: {todoist_id} ({item.get("content", "")})')
            continue

        existing_path = todoist_id_cache.get(todoist_id)
        if existing_path:
            stats.skipped_duplicate += 1
            stats.skipped_duplicate_items.append({
                'todoist_id': todoist_id,
                'task_path': existing_path,
            })
            created_paths[todoist_id] = existing_path
            print(f'SKIP duplicate: {todoist_id} -> {existing_path}')
            continue

        parent_id = item.get('parent_id')
        parent_task_path = created_paths.get(parent_id) if parent_id else None
        if parent_id and args['subtasks_mode'] != 'metadata-only' and not parent_task_path:
            parent_task_path = todoist_id_cache.get(parent_id)

        payload = build_payload(
            item,
            indexes,
            subtasks_mode=args['subtasks_mode'],
            parent_task_path=parent_task_path,
        )

        if args['dry_run']:
            stats.created += 1
            processed += 1
            print(f'DRY-RUN create: {todoist_id} ({item.get("content", "")})')
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            continue

        project = indexes['projects'].get(item.get('project_id'))
        project_name = project.get('name') if isinstance(project, dict) else None
        if project_name:
            ensure_project_note_exists(args['vault_root'], str(project_name))

        success, result, body = create_task(args['api_base'], args['api_token'], payload)
        if success:
            stats.created += 1
            processed += 1
            created_paths[todoist_id] = result
            todoist_id_cache[todoist_id] = result
            stats.created_items.append({
                'todoist_id': todoist_id,
                'task_path': result,
                'title': item.get('content', ''),
            })
            print(f'CREATED: {todoist_id} -> {result}')
            continue

        stats.failed += 1
        stats.failed_items.append({
            'todoist_id': todoist_id,
            'error': result,
        })
        print(f'FAILED: {todoist_id}: {result}', file=sys.stderr)
        if args['stop_on_error']:
            break

    finished_at = datetime.now(timezone.utc)
    write_report(
        args['report'],
        started_at=started_at,
        finished_at=finished_at,
        stats=stats,
        dry_run=args['dry_run'],
        limit=args['limit'],
        subtasks_mode=args['subtasks_mode'],
        json_path=args['json_path'],
        api_base=args['api_base'],
    )

    print('\n=== Migration summary ===')
    print(f'total: {stats.total}')
    print(f'skipped_deleted: {stats.skipped_deleted}')
    print(f'skipped_completed: {stats.skipped_completed}')
    print(f'skipped_duplicate: {stats.skipped_duplicate}')
    print(f'created: {stats.created}')
    print(f'failed: {stats.failed}')
    print(f'Report written to: {args["report"]}')

    return 1 if stats.failed else 0


def main() -> int:
    args = parse_args()
    return migrate(args)


if __name__ == '__main__':
    raise SystemExit(main())
