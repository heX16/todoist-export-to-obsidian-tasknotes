#!/usr/bin/env python3
"""TaskNotes Obsidian plugin data.json configuration helpers."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from todoist_tasknotes_mapping import DEFAULT_API_BASE, TODOIST_ID_FIELD_KEY

TODOIST_ID_USER_FIELD_ID = 'todoist-id'
TODOIST_ID_USER_FIELD_DISPLAY_NAME = 'Todoist ID'
TODOIST_ID_USER_FIELD_TYPE = 'text'

TODOIST_ID_USER_FIELD: dict[str, str] = {
    'id': TODOIST_ID_USER_FIELD_ID,
    'displayName': TODOIST_ID_USER_FIELD_DISPLAY_NAME,
    'key': TODOIST_ID_FIELD_KEY,
    'type': TODOIST_ID_USER_FIELD_TYPE,
}

TASKNOTES_DATA_BACKUP_NAME = 'tasknotes-data.json.bak'


def tasknotes_data_backup_path() -> Path:
    return Path.cwd() / TASKNOTES_DATA_BACKUP_NAME


def tasknotes_data_json_path(vault_root: Path) -> Path:
    return vault_root / '.obsidian' / 'plugins' / 'tasknotes' / 'data.json'


def load_tasknotes_data(vault_root: Path) -> dict[str, Any]:
    data_json_path = tasknotes_data_json_path(vault_root)
    if not data_json_path.is_file():
        raise SystemExit(f'ERROR: TaskNotes data.json not found: {data_json_path}')

    with data_json_path.open(encoding='utf-8') as handle:
        return json.load(handle)


def load_api_auth_token(vault_root: Path) -> str | None:
    """Read apiAuthToken from TaskNotes data.json, or None if unset."""
    data = load_tasknotes_data(vault_root)
    token = data.get('apiAuthToken')
    if token is None:
        return None
    return str(token)


def parse_api_port(api_base: str) -> int:
    parsed = urlparse(api_base)
    if parsed.port is not None:
        return parsed.port
    if parsed.scheme == 'https':
        return 443
    return 80


def _has_todoist_id_user_field(user_fields: list[Any]) -> bool:
    for field in user_fields:
        if isinstance(field, dict) and field.get('key') == TODOIST_ID_FIELD_KEY:
            return True
    return False


def apply_tasknotes_obsidian_config(
    vault_root: Path,
    *,
    api_token: str | None,
    api_base: str = DEFAULT_API_BASE,
) -> dict[str, bool]:
    """
    Update TaskNotes data.json for migration: userFields, HTTP API, token, port.

    Returns a report dict with keys: added_user_field, enabled_api, updated_token,
    updated_port, unchanged.
    """
    if not vault_root.exists() or not vault_root.is_dir():
        raise SystemExit(f'ERROR: Vault root directory does not exist: {vault_root}')

    data_json_path = tasknotes_data_json_path(vault_root)
    data = load_tasknotes_data(vault_root)

    report = {
        'added_user_field': False,
        'enabled_api': False,
        'updated_token': False,
        'updated_port': False,
        'unchanged': False,
    }

    user_fields = data.get('userFields')
    if not isinstance(user_fields, list):
        user_fields = []
        data['userFields'] = user_fields

    if not _has_todoist_id_user_field(user_fields):
        user_fields.append(dict(TODOIST_ID_USER_FIELD))
        report['added_user_field'] = True

    if not data.get('enableAPI'):
        data['enableAPI'] = True
        report['enabled_api'] = True

    target_port = parse_api_port(api_base)
    if data.get('apiPort') != target_port:
        data['apiPort'] = target_port
        report['updated_port'] = True

    if api_token is not None and data.get('apiAuthToken') != api_token:
        data['apiAuthToken'] = api_token
        report['updated_token'] = True

    changed = any(report[key] for key in report if key != 'unchanged')
    if not changed:
        report['unchanged'] = True
        print(f'TaskNotes config already up to date: {data_json_path}')
        return report

    backup_path = tasknotes_data_backup_path()
    shutil.copy2(data_json_path, backup_path)

    serialized = json.dumps(data, indent=2, ensure_ascii=False) + '\n'
    data_json_path.write_text(serialized, encoding='utf-8')

    changes: list[str] = []
    if report['added_user_field']:
        changes.append(f'added user field {TODOIST_ID_FIELD_KEY!r}')
    if report['enabled_api']:
        changes.append('enabled HTTP API')
    if report['updated_token']:
        changes.append('updated apiAuthToken')
    if report['updated_port']:
        changes.append(f'updated apiPort to {target_port}')

    print(f'Updated TaskNotes config: {data_json_path}')
    print(f'  Backup: {backup_path}')
    print(f'  Changes: {", ".join(changes)}')
    print(
        'Reload TaskNotes after changing data.json '
        '(disable/enable plugin or restart Obsidian).',
        file=sys.stderr,
    )

    return report
