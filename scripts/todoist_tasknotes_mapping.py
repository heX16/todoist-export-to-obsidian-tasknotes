#!/usr/bin/env python3
"""Shared Todoist JSON -> TaskNotes API mapping utilities."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Literal

from todoist_projects import parent_project_link, project_wikilink

DEFAULT_API_BASE = 'http://127.0.0.1:16876'
DEFAULT_API_TOKEN = 'tasknotes-token'
DEFAULT_JSON_PATH = Path(__file__).resolve().parent.parent / 'source-todoist' / 'todoist.json'
TODOIST_ID_FIELD_KEY = 'todoist_id'

SubtasksMode = Literal['native-project-link', 'metadata-only', 'parent-project-only']

# Todoist priority: 1 = default, 4 = highest (red flag).
TODOIST_PRIORITY_TO_TASKNOTES = {
    1: 'none',
    2: 'low',
    3: 'normal',
    4: 'high',
}

def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding='utf-8') as handle:
        return json.load(handle)


def build_indexes(data: dict[str, Any]) -> dict[str, Any]:
    labels_by_id = {
        str(label['id']): label
        for label in data.get('labels', [])
        if not label.get('is_deleted')
    }
    labels_by_name = {
        label['name']: label
        for label in labels_by_id.values()
    }

    return {
        'projects': {
            str(project['id']): project
            for project in data.get('projects', [])
        },
        'sections': {
            str(section['id']): section
            for section in data.get('sections', [])
        },
        'items': {
            str(item['id']): item
            for item in data.get('items', [])
        },
        'collaborators': {
            str(collaborator['id']): collaborator
            for collaborator in data.get('collaborators', [])
        },
        'labels_by_id': labels_by_id,
        'labels_by_name': labels_by_name,
        'notes_by_item_id': _index_notes(data.get('notes', [])),
        'project_notes_by_project_id': _index_project_notes(data.get('project_notes', [])),
    }


def _index_notes(notes: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    indexed: dict[str, list[dict[str, Any]]] = {}
    for note in notes:
        if note.get('is_deleted'):
            continue
        item_id = note.get('item_id')
        if item_id is None:
            continue
        indexed.setdefault(str(item_id), []).append(note)
    return indexed


def _index_project_notes(notes: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    indexed: dict[str, list[dict[str, Any]]] = {}
    for note in notes:
        if note.get('is_deleted'):
            continue
        project_id = note.get('project_id')
        if project_id is None:
            continue
        indexed.setdefault(str(project_id), []).append(note)
    return indexed


def resolve_label_names(item: dict[str, Any], indexes: dict[str, Any]) -> list[str]:
    resolved: list[str] = []
    for label in item.get('labels') or []:
        label_key = str(label)
        if label_key.isnumeric() and label_key in indexes['labels_by_id']:
            resolved.append(indexes['labels_by_id'][label_key]['name'])
        elif label in indexes['labels_by_name']:
            resolved.append(indexes['labels_by_name'][label]['name'])
        else:
            resolved.append(str(label))
    return resolved


def resolve_user_name(user_id: Any, indexes: dict[str, Any]) -> str | None:
    if user_id is None:
        return None
    collaborator = indexes['collaborators'].get(str(user_id))
    if collaborator is None:
        return str(user_id)
    return collaborator.get('full_name') or collaborator.get('email') or str(user_id)


def map_priority(priority: int | None) -> str:
    return TODOIST_PRIORITY_TO_TASKNOTES.get(priority or 1, 'normal')


def map_status(checked: bool) -> str:
    return 'done' if checked else 'open'


def extract_due_date(due: dict[str, Any] | None) -> str | None:
    if not due:
        return None
    return due.get('date')


def format_duration_minutes(duration: dict[str, Any] | None) -> int | None:
    if not duration:
        return None
    amount = duration.get('amount')
    unit = duration.get('unit')
    if amount is None or unit is None:
        return None
    if unit == 'minute':
        return int(amount)
    if unit == 'hour':
        return int(amount) * 60
    if unit == 'day':
        return int(amount) * 24 * 60
    return None


def extract_todoist_id_from_task_data(task_data: dict[str, Any]) -> str | None:
    """Read todoist_id from TaskNotes customProperties or top-level task field."""
    custom_properties = task_data.get('customProperties') or {}
    todoist_id = custom_properties.get(TODOIST_ID_FIELD_KEY)
    if todoist_id:
        return str(todoist_id)

    top_level = task_data.get(TODOIST_ID_FIELD_KEY)
    if top_level:
        return str(top_level)

    return None


def build_details(
    item: dict[str, Any],
    indexes: dict[str, Any],
    *,
    migration_marker: str | None = None,
) -> str:
    notes = indexes['notes_by_item_id'].get(str(item['id']), [])

    lines: list[str] = []
    if migration_marker:
        lines.extend([f'[{migration_marker}]', ''])

    description = (item.get('description') or '').strip()
    if description:
        lines.extend([description, ''])

    if notes:
        if lines:
            lines.append('')
        lines.append('## Todoist notes')
        for note in notes:
            lines.append(f'- {note.get("content", "").strip()}')
            attachment = note.get('file_attachment')
            if attachment:
                lines.append(f'  - attachment: `{json.dumps(attachment, ensure_ascii=False)}`')

    if not lines:
        return ''
    return '\n'.join(lines).strip() + '\n'


def build_payload(
    item: dict[str, Any],
    indexes: dict[str, Any],
    *,
    migration_marker: str | None = None,
    subtasks_mode: SubtasksMode = 'metadata-only',
    parent_task_path: str | None = None,
) -> dict[str, Any]:
    project = indexes['projects'].get(str(item.get('project_id')))
    label_names = resolve_label_names(item, indexes)
    time_estimate = format_duration_minutes(item.get('duration'))

    details = build_details(item, indexes, migration_marker=migration_marker)
    todoist_id = str(item['id'])

    payload: dict[str, Any] = {
        'title': item['content'],
        'status': map_status(bool(item.get('checked'))),
        'priority': map_priority(item.get('priority')),
        TODOIST_ID_FIELD_KEY: todoist_id,
        'customProperties': {
            TODOIST_ID_FIELD_KEY: todoist_id,
        },
    }

    if details:
        payload['details'] = details

    due_date = extract_due_date(item.get('due'))
    if due_date:
        payload['due'] = due_date

    if label_names:
        payload['tags'] = label_names

    parent_id = item.get('parent_id')
    is_subtask = bool(parent_id)

    projects: list[str] = []
    if is_subtask:
        if subtasks_mode != 'metadata-only' and parent_task_path:
            projects.append(parent_project_link(parent_task_path))
    elif subtasks_mode == 'parent-project-only' and parent_task_path:
        projects.append(parent_project_link(parent_task_path))
    elif project and project.get('name'):
        projects.append(project_wikilink(project['name']))

    if projects:
        payload['projects'] = projects

    if time_estimate is not None:
        payload['timeEstimate'] = time_estimate

    return payload


def api_request(
    method: str,
    url: str,
    token: str,
    payload: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json',
    }
    data = None
    if payload is not None:
        headers['Content-Type'] = 'application/json'
        data = json.dumps(payload, ensure_ascii=False).encode('utf-8')

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request) as response:
            body = response.read().decode('utf-8')
            return response.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as error:
        body = error.read().decode('utf-8')
        try:
            parsed = json.loads(body) if body else {'error': error.reason}
        except json.JSONDecodeError:
            parsed = {'error': body or error.reason}
        return error.code, parsed


def list_all_task_paths(api_base: str, api_token: str) -> list[str]:
    paths: list[str] = []
    offset = 0
    limit = 200

    while True:
        url = f'{api_base}/api/tasks?limit={limit}&offset={offset}'
        status, body = api_request('GET', url, api_token)
        if status != 200 or not body.get('success'):
            raise RuntimeError(f'Failed to list tasks at offset {offset}: HTTP {status} {body}')

        data = body.get('data', {})
        tasks = data.get('tasks', [])
        for task in tasks:
            task_path = task.get('path') or task.get('id')
            if task_path:
                paths.append(task_path)

        pagination = data.get('pagination', {})
        if not pagination.get('hasMore'):
            break
        offset += limit

    return paths


def build_todoist_id_cache(api_base: str, api_token: str) -> dict[str, str]:
    """Map todoist_id -> TaskNotes task path by scanning existing tasks."""
    cache: dict[str, str] = {}
    paths = list_all_task_paths(api_base, api_token)

    for task_path in paths:
        encoded_path = urllib.parse.quote(task_path, safe='')
        status, body = api_request('GET', f'{api_base}/api/tasks/{encoded_path}', api_token)
        if status != 200 or not body.get('success'):
            continue

        task_data = body.get('data', {})
        todoist_id = extract_todoist_id_from_task_data(task_data)
        if todoist_id:
            cache[todoist_id] = task_path

    return cache
