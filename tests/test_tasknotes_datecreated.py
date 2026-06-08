"""Integration test: TaskNotes API dateCreated round-trip.

Creates a task with a client-provided dateCreated, reads it back, verifies
the stored value matches the requested one, then deletes the task.

Default pytest run excludes this module (see pytest.ini). Run explicitly with::

    pytest -m integration
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import pytest

import testdata  # noqa: F401

from tasknotes_api_testlib import (  # noqa: E402
    TASKNOTES_API_TOKEN_ENV,
    api_is_available,
    create_task,
    delete_task,
    integration_api_token,
    iso_now_for_title,
    read_task,
)
from todoist_tasknotes_mapping import DEFAULT_API_BASE  # noqa: E402

DEFAULT_TEST_DATE_CREATED = '2000-01-02T03:04:05Z'


def verify_date_created_roundtrip(
    api_base: str,
    api_token: str,
    *,
    date_created: str,
    title: str | None = None,
    delete_after: bool = True,
) -> tuple[str, str | None, str]:
    """Create a task, read it back, optionally delete it, return (requested, stored, task_path)."""
    requested_date_created = str(date_created)
    task_title = title or f'dateCreated API test {iso_now_for_title()}'

    create_payload: dict[str, Any] = {
        'title': task_title,
        'details': f'Requested dateCreated: {requested_date_created}\n',
        'dateCreated': requested_date_created,
    }

    task_path, _create_data = create_task(api_base, api_token, create_payload)
    try:
        task_data = read_task(api_base, api_token, task_path)
        stored_date_created = task_data.get('dateCreated')
        return requested_date_created, stored_date_created, task_path
    finally:
        if delete_after:
            delete_task(api_base, api_token, task_path)


@pytest.mark.integration
def test_date_created_preserved_by_api() -> None:
    api_token = integration_api_token()
    if api_token is None:
        pytest.skip(f'{TASKNOTES_API_TOKEN_ENV} is not set')
    if not api_is_available(DEFAULT_API_BASE, api_token):
        pytest.skip(f'TaskNotes API is not reachable at {DEFAULT_API_BASE}')

    requested, stored, _task_path = verify_date_created_roundtrip(
        DEFAULT_API_BASE,
        api_token,
        date_created=DEFAULT_TEST_DATE_CREATED,
    )
    assert stored == requested, (
        f'dateCreated mismatch: requested {requested!r}, stored {stored!r}'
    )


def main() -> int:
    parser = argparse.ArgumentParser(description='Test TaskNotes dateCreated behavior.')
    parser.add_argument('--api-base', default=DEFAULT_API_BASE)
    parser.add_argument('--api-token', required=True)
    parser.add_argument(
        '--date-created',
        default=DEFAULT_TEST_DATE_CREATED,
        help='ISO datetime string to send as dateCreated (e.g. 2026-06-08T00:00:00Z).',
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

    create_payload_preview = {
        'title': args.title or f'dateCreated API test {iso_now_for_title()}',
        'details': f'Requested dateCreated: {args.date_created}\n',
        'dateCreated': str(args.date_created),
    }
    print('=== POST /api/tasks payload ===')
    print(json.dumps(create_payload_preview, indent=2, ensure_ascii=False))

    try:
        requested_date_created, stored_date_created, task_path = verify_date_created_roundtrip(
            args.api_base,
            args.api_token,
            date_created=str(args.date_created),
            title=args.title,
            delete_after=not args.keep,
        )
    except RuntimeError as error:
        print(f'\nRESULT: {error}', file=sys.stderr)
        return 2

    print('\n=== Comparison ===')
    print(f'- requested dateCreated: {requested_date_created}')
    print(f'- stored dateCreated:    {stored_date_created}')
    print(f'- task path:             {task_path}')

    if stored_date_created == requested_date_created:
        print('\nRESULT: dateCreated was preserved exactly.')
        return 0

    if stored_date_created:
        print('\nRESULT: dateCreated differs (likely ignored or overwritten by TaskNotes).')
        return 1

    print('\nRESULT: dateCreated is missing in response (unexpected).')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
