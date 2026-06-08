"""Integration test: TaskNotes API scheduled suppression.

Creates a task with ``scheduled`` set to ``""`` or ``None``, reads it back,
and verifies TaskNotes did not persist a scheduled date (field absent or empty).

Default pytest run excludes this module (see pytest.ini). Run explicitly with::

    pytest -m integration tests/test_tasknotes_scheduled.py
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import pytest

import testdata  # noqa: F401

from tasknotes_api_testlib import (  # noqa: E402
    api_is_available,
    create_task,
    delete_task,
    iso_now_for_title,
    read_task,
)
from todoist_tasknotes_mapping import (  # noqa: E402
    DEFAULT_API_BASE,
    DEFAULT_API_TOKEN,
)


def scheduled_is_absent(task_data: dict[str, Any]) -> bool:
    """Return True when the API response has no meaningful scheduled value."""
    if 'scheduled' not in task_data:
        return True
    value = task_data.get('scheduled')
    return value is None or value == ''


def verify_scheduled_suppressed_roundtrip(
    api_base: str,
    api_token: str,
    *,
    scheduled_value: str | None,
    title: str | None = None,
    delete_after: bool = True,
) -> tuple[dict[str, Any], str]:
    """Create a task, read it back, optionally delete it, return (task_data, path)."""
    task_title = title or f'scheduled API test {scheduled_value!r} {iso_now_for_title()}'

    create_payload: dict[str, Any] = {
        'title': task_title,
        'details': f'Requested scheduled: {scheduled_value!r}\n',
        'scheduled': scheduled_value,
    }

    task_path, _create_data = create_task(api_base, api_token, create_payload)
    try:
        task_data = read_task(api_base, api_token, task_path)
        return task_data, task_path
    finally:
        if delete_after:
            delete_task(api_base, api_token, task_path)


@pytest.mark.integration
@pytest.mark.parametrize('scheduled_value', ['', None])
def test_scheduled_empty_or_none_not_persisted(scheduled_value: str | None) -> None:
    if not api_is_available(DEFAULT_API_BASE, DEFAULT_API_TOKEN):
        pytest.skip(f'TaskNotes API is not reachable at {DEFAULT_API_BASE}')

    task_data, _task_path = verify_scheduled_suppressed_roundtrip(
        DEFAULT_API_BASE,
        DEFAULT_API_TOKEN,
        scheduled_value=scheduled_value,
    )
    assert scheduled_is_absent(task_data), (
        f'scheduled should be absent or empty when sent as {scheduled_value!r}, '
        f'got {task_data.get("scheduled")!r} (keys: {sorted(task_data)})'
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Test TaskNotes scheduled="" / scheduled=null behavior.',
    )
    parser.add_argument('--api-base', default=DEFAULT_API_BASE)
    parser.add_argument('--api-token', default=DEFAULT_API_TOKEN)
    parser.add_argument(
        '--scheduled',
        choices=('empty', 'null'),
        default='empty',
        help='Send scheduled as "" (empty) or null (None). Default: empty.',
    )
    parser.add_argument(
        '--title',
        default=None,
        help='Optional task title. If omitted, a unique test title is generated.',
    )
    parser.add_argument(
        '--keep',
        action='store_true',
        help='Keep the created task instead of deleting it after the check.',
    )
    args = parser.parse_args()

    if not api_is_available(args.api_base, args.api_token):
        print(f'RESULT: TaskNotes API is not reachable at {args.api_base}.', file=sys.stderr)
        return 4

    scheduled_value: str | None = '' if args.scheduled == 'empty' else None
    create_payload_preview = {
        'title': args.title or f'scheduled API test {scheduled_value!r} {iso_now_for_title()}',
        'details': f'Requested scheduled: {scheduled_value!r}\n',
        'scheduled': scheduled_value,
    }
    print('=== POST /api/tasks payload ===')
    print(json.dumps(create_payload_preview, indent=2, ensure_ascii=False))

    try:
        task_data, task_path = verify_scheduled_suppressed_roundtrip(
            args.api_base,
            args.api_token,
            scheduled_value=scheduled_value,
            title=args.title,
            delete_after=not args.keep,
        )
    except RuntimeError as error:
        print(f'\nRESULT: {error}', file=sys.stderr)
        return 2

    stored_scheduled = task_data.get('scheduled')
    scheduled_key_present = 'scheduled' in task_data

    print('\n=== Comparison ===')
    print(f'- requested scheduled: {scheduled_value!r}')
    print(f'- scheduled key present: {scheduled_key_present}')
    print(f'- stored scheduled:      {stored_scheduled!r}')
    print(f'- task path:             {task_path}')

    if scheduled_is_absent(task_data):
        print('\nRESULT: scheduled was not persisted (absent or empty).')
        return 0

    print('\nRESULT: scheduled was persisted (TaskNotes likely applied a default date).')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
