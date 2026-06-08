"""Shared helpers for TaskNotes HTTP API integration tests."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from todoist_tasknotes_mapping import api_request

API_HEALTH_TIMEOUT_SECONDS = 2
TASKNOTES_API_TOKEN_ENV = 'TASKNOTES_API_TOKEN'


def integration_api_token() -> str | None:
    token = os.environ.get(TASKNOTES_API_TOKEN_ENV, '').strip()
    return token or None


def iso_now_for_title() -> str:
    return datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')


def extract_task_path(create_response: dict[str, Any]) -> str:
    data = create_response.get('data', {}) if isinstance(create_response, dict) else {}
    path = data.get('path') or data.get('id')
    if not path:
        raise RuntimeError(f'No task path in response: {json.dumps(create_response, ensure_ascii=False)}')
    return str(path)


def encoded_task_url(api_base: str, task_path: str) -> str:
    encoded_path = urllib.parse.quote(task_path, safe='')
    return f'{api_base}/api/tasks/{encoded_path}'


def delete_task(api_base: str, api_token: str, task_path: str) -> None:
    status, body = api_request('DELETE', encoded_task_url(api_base, task_path), api_token)
    if status in (200, 204) and (status == 204 or body.get('success')):
        return
    raise RuntimeError(
        f'Failed to delete test task: HTTP {status} {json.dumps(body, ensure_ascii=False)}'
    )


def api_is_available(api_base: str, api_token: str) -> bool:
    url = f'{api_base.rstrip("/")}/api/health'
    request = urllib.request.Request(
        url,
        headers={
            'Authorization': f'Bearer {api_token}',
            'Accept': 'application/json',
        },
        method='GET',
    )
    try:
        with urllib.request.urlopen(request, timeout=API_HEALTH_TIMEOUT_SECONDS) as response:
            if response.status != 200:
                return False
            body = json.loads(response.read().decode('utf-8'))
            return bool(body.get('success'))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
        return False


def create_task(
    api_base: str,
    api_token: str,
    payload: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    """Create a task and return ``(task_path, create_response_data)``."""
    status, body = api_request('POST', f'{api_base}/api/tasks', api_token, payload)
    if status != 201 or not body.get('success'):
        raise RuntimeError(
            f'Failed to create task: HTTP {status} {json.dumps(body, ensure_ascii=False)}'
        )
    task_path = extract_task_path(body)
    data = body.get('data', {}) or {}
    return task_path, data if isinstance(data, dict) else {}


def read_task(api_base: str, api_token: str, task_path: str) -> dict[str, Any]:
    """Read one task and return its ``data`` object."""
    status, body = api_request('GET', encoded_task_url(api_base, task_path), api_token)
    if status != 200 or not body.get('success'):
        raise RuntimeError(
            f'Failed to read task: HTTP {status} {json.dumps(body, ensure_ascii=False)}'
        )
    task_data = body.get('data', {}) or {}
    return task_data if isinstance(task_data, dict) else {}
