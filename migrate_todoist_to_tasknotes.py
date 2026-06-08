#!/usr/bin/env python3
"""Migrate Todoist JSON export into TaskNotes via HTTP API."""

from __future__ import annotations

import json
import sys
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TextIO, cast

from docopt import docopt

REPO_ROOT = Path(__file__).resolve().parent
SCRIPTS_DIR = REPO_ROOT / 'scripts'
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from todoist_projects import ensure_project_note_exists, parent_project_link  # noqa: E402
from todoist_tasknotes_mapping import (  # noqa: E402
    DEFAULT_API_BASE,
    DEFAULT_JSON_PATH,
    api_request,
    build_indexes,
    build_payload,
    build_todoist_id_cache,
    load_json,
)

DEFAULT_VAULT_ROOT = REPO_ROOT / 'target-obsidian'

USAGE = f'''Migrate Todoist JSON export into TaskNotes via HTTP API.

Usage:
  migrate_todoist_to_tasknotes.py --api-token=<token> [options]
  migrate_todoist_to_tasknotes.py (-h | --help)

Options:
  -h --help                           Show this help.
  --json-path=<path>                  Path to Todoist JSON export.
                                      [default: {DEFAULT_JSON_PATH}]
  --api-base=<url>                    TaskNotes API base URL.
                                      [default: {DEFAULT_API_BASE}]
  --api-token=<token>                 TaskNotes API token (required).
  --vault-root=<path>                 Obsidian vault root directory (for creating project notes directly).
                                      [default: {DEFAULT_VAULT_ROOT}]
  --dry-run                           Do not call API; print would-be payloads.
  --limit=<n>                         Process at most N new task creations.
  --include-deleted                   Include deleted Todoist items.
  --include-completed                 Include completed Todoist items (default).
  --no-include-completed              Exclude completed Todoist items.
  --stop-on-error                     Stop at first failed task creation.
  --report-format=<format>            Final report format printed to stdout.
                                      One of: human, json
                                      [default: human]
'''


@dataclass
class MigrationStats:
    total: int = 0
    skipped_deleted: int = 0
    skipped_completed: int = 0
    skipped_duplicate: int = 0
    created: int = 0
    failed: int = 0


Args = dict[str, Any]


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

    report_format = str(options['--report-format'])
    if report_format not in ('human', 'json'):
        raise SystemExit('ERROR: --report-format must be one of: human, json')

    api_token = options['--api-token']
    if not api_token:
        raise SystemExit('ERROR: --api-token is required')

    return {
        'json_path': Path(options['--json-path']),
        'api_base': str(options['--api-base']),
        'api_token': str(api_token),
        'vault_root': Path(options['--vault-root']),
        'dry_run': bool(options['--dry-run']),
        'limit': limit,
        'include_deleted': bool(options['--include-deleted']),
        'include_completed': not bool(options['--no-include-completed']),
        'stop_on_error': bool(options['--stop-on-error']),
        'report_format': report_format,
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


def get_task_data(
    api_base: str,
    api_token: str,
    task_path: str,
) -> tuple[bool, dict[str, Any] | str]:
    encoded_path = urllib.parse.quote(task_path, safe='')
    status, body = api_request('GET', f'{api_base}/api/tasks/{encoded_path}', api_token)
    if status == 200 and body.get('success'):
        return True, body.get('data', {})

    error_message = body.get('error') or json.dumps(body, ensure_ascii=False)
    return False, error_message


def update_task_projects(
    api_base: str,
    api_token: str,
    task_path: str,
    projects: list[str],
) -> tuple[bool, str]:
    encoded_path = urllib.parse.quote(task_path, safe='')
    status, body = api_request(
        'PUT',
        f'{api_base}/api/tasks/{encoded_path}',
        api_token,
        {'projects': projects},
    )
    if status == 200 and body.get('success'):
        return True, task_path

    error_message = body.get('error') or json.dumps(body, ensure_ascii=False)
    return False, error_message


def append_parent_link_projects(existing_projects: list[str], parent_link: str) -> list[str]:
    if parent_link in existing_projects:
        return existing_projects
    return [*existing_projects, parent_link]


def attach_missing_parent_links(
    *,
    items: list[dict[str, Any]],
    api_base: str,
    api_token: str,
    include_deleted: bool,
    include_completed: bool,
    stop_on_error: bool,
) -> int:
    """Pass 2: append missing parent wiki-links to subtask projects (idempotent)."""
    print('Pass 2: rebuilding todoist_id cache for parent linking...')
    todoist_id_cache = build_todoist_id_cache(api_base, api_token)
    print(f'Pass 2: {len(todoist_id_cache)} tasks in cache.')

    errors = 0
    for item in items:
        parent_id = item.get('parent_id')
        if not parent_id:
            continue

        skip_reason = should_skip_item(
            item,
            include_deleted=include_deleted,
            include_completed=include_completed,
        )
        if skip_reason:
            continue

        todoist_id = item['id']
        child_path = todoist_id_cache.get(todoist_id)
        if not child_path:
            print(f'SKIP link parent (child not in vault): {todoist_id} ({item.get("content", "")})')
            continue

        parent_path = todoist_id_cache.get(parent_id)
        if not parent_path:
            print(
                f'SKIP link parent (parent not in vault): {todoist_id} '
                f'parent={parent_id} ({item.get("content", "")})',
            )
            continue

        expected_parent_link = parent_project_link(parent_path)
        success, task_data = get_task_data(api_base, api_token, child_path)
        if not success:
            errors += 1
            print(f'FAILED link parent GET: {todoist_id}: {task_data}', file=sys.stderr)
            if stop_on_error:
                break
            continue

        existing_projects = list((task_data or {}).get('projects') or [])
        if expected_parent_link in existing_projects:
            continue

        merged_projects = append_parent_link_projects(existing_projects, expected_parent_link)
        update_success, update_result = update_task_projects(
            api_base,
            api_token,
            child_path,
            merged_projects,
        )
        if update_success:
            print(f'LINKED parent: {todoist_id} -> {expected_parent_link} on {child_path}')
            continue

        errors += 1
        print(f'FAILED link parent PUT: {todoist_id}: {update_result}', file=sys.stderr)
        if stop_on_error:
            break

    return errors


def build_report_data(
    *,
    stats: MigrationStats,
    dry_run: bool,
    limit: int | None,
    json_path: Path,
    api_base: str,
) -> dict[str, Any]:
    partial = limit is not None

    return {
        'dry_run': dry_run,
        'partial_run': partial,
        'limit': limit,
        'json_source': str(json_path),
        'api_base': api_base,
        'summary': {
            'total': stats.total,
            'skipped_deleted': stats.skipped_deleted,
            'skipped_completed': stats.skipped_completed,
            'skipped_duplicate': stats.skipped_duplicate,
            'created': stats.created,
            'failed': stats.failed,
        },
    }


def render_report_human(report: dict[str, Any]) -> str:
    summary = cast(dict[str, Any], report['summary'])

    lines = [
        '# Todoist -> TaskNotes migration run report',
        '',
        f'- Dry run: {report["dry_run"]}',
        f'- Partial run: {report["partial_run"]}',
        f'- Limit: {report["limit"] if report["limit"] is not None else "none"}',
        f'- JSON source: `{report["json_source"]}`',
        f'- API base: `{report["api_base"]}`',
        '',
        '## Summary',
        '',
        f'- total: {summary["total"]}',
        f'- skipped_deleted: {summary["skipped_deleted"]}',
        f'- skipped_completed: {summary["skipped_completed"]}',
        f'- skipped_duplicate: {summary["skipped_duplicate"]}',
        f'- created: {summary["created"]}',
        f'- failed: {summary["failed"]}',
        '',
    ]

    return '\n'.join(lines)


def render_report_json(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, ensure_ascii=False)


def migrate(args: Args) -> int:
    stats_total: int | None = None
    current_index: int | None = None

    def print_item_status(
        label: str,
        todoist_id: str,
        *,
        title: str | None = None,
        detail: str | None = None,
        detail_sep: str = ' ',
        file: TextIO = sys.stdout,
    ) -> None:
        nonlocal stats_total, current_index

        prefix = ''
        if current_index is not None and stats_total is not None:
            prefix = f'[{current_index}/{stats_total}] '

        message = f'{prefix}{label}: {todoist_id}'
        if detail:
            message += f'{detail_sep}{detail}'
        if title:
            message += f' ({title})'
        print(message, file=file)

    data = load_json(args['json_path'])
    indexes = build_indexes(data)
    items = list(data.get('items', []))

    stats = MigrationStats(total=len(items))
    stats_total = stats.total
    todoist_id_cache: dict[str, str] = {}
    created_paths: dict[str, str] = {}

    if not args['dry_run']:
        health_status, health_body = api_request('GET', f'{args["api_base"]}/api/health', args["api_token"])
        if health_status != 200 or not health_body.get('success'):
            print('ERROR: TaskNotes API health check failed.', file=sys.stderr)
            print(json.dumps(health_body, indent=2, ensure_ascii=False), file=sys.stderr)
            return 1

        print('Pass 1: building todoist_id cache from existing TaskNotes tasks...')
        todoist_id_cache = build_todoist_id_cache(args['api_base'], args['api_token'])
        print(f'Pass 1: found {len(todoist_id_cache)} previously imported tasks.')

    processed = 0
    for index, item in enumerate(items, start=1):
        current_index = index
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
            print_item_status(
                'SKIP deleted',
                todoist_id,
                title=item.get('content', ''),
            )
            continue
        if skip_reason == 'completed':
            stats.skipped_completed += 1
            print_item_status(
                'SKIP completed',
                todoist_id,
                title=item.get('content', ''),
            )
            continue

        existing_path = todoist_id_cache.get(todoist_id)
        if existing_path:
            stats.skipped_duplicate += 1
            created_paths[todoist_id] = existing_path
            print_item_status(
                'SKIP duplicate',
                todoist_id,
                detail=existing_path,
                detail_sep=' -> ',
            )
            continue

        parent_id = item.get('parent_id')
        parent_task_path = created_paths.get(parent_id) if parent_id else None
        if parent_id and not parent_task_path:
            parent_task_path = todoist_id_cache.get(parent_id)

        payload = build_payload(
            item,
            indexes,
            parent_task_path=parent_task_path,
        )

        added_at = item.get('added_at')
        if added_at:
            payload['dateCreated'] = str(added_at)

        if args['dry_run']:
            stats.created += 1
            processed += 1
            print_item_status(
                'DRY-RUN create',
                todoist_id,
                title=item.get('content', ''),
            )
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
            print_item_status(
                'CREATED',
                todoist_id,
                detail=result,
                detail_sep=' -> ',
            )
            continue

        stats.failed += 1
        print_item_status(
            'FAILED',
            todoist_id,
            detail=result,
            detail_sep=': ',
            file=sys.stderr,
        )
        if args['stop_on_error']:
            break

    link_errors = 0
    if not args['dry_run']:
        link_errors = attach_missing_parent_links(
            items=items,
            api_base=args['api_base'],
            api_token=args['api_token'],
            include_deleted=args['include_deleted'],
            include_completed=args['include_completed'],
            stop_on_error=args['stop_on_error'],
        )
    else:
        print('DRY-RUN: skipping pass 2 (parent link attachment).')

    report = build_report_data(
        stats=stats,
        dry_run=args['dry_run'],
        limit=args['limit'],
        json_path=args['json_path'],
        api_base=args['api_base'],
    )

    report_format = str(args.get('report_format', 'human'))
    if report_format == 'human':
        print('\n' + render_report_human(report))
    elif report_format == 'json':
        print(render_report_json(report))

    return 1 if stats.failed or link_errors else 0


def main() -> int:
    args = parse_args()
    return migrate(args)


if __name__ == '__main__':
    raise SystemExit(main())
