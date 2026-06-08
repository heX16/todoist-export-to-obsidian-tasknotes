"""Dry-run migration flow tests."""

from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import testdata  # noqa: F401
from testdata import MINIMAL_FIXTURE_PATH

import migrate_todoist_to_tasknotes as migrator


def _extract_dry_run_payload(output: str, todoist_id: str) -> dict:
    marker = f'DRY-RUN create: {todoist_id}'
    brace_start = output.index('{', output.index(marker))
    depth = 0
    for index, char in enumerate(output[brace_start:], brace_start):
        if char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                return json.loads(output[brace_start:index + 1])
    raise ValueError(f'No JSON payload found for todoist id {todoist_id}')


def _dry_run_args(report_path: Path, **overrides) -> migrator.Args:
    base: migrator.Args = {
        'json_path': MINIMAL_FIXTURE_PATH,
        'api_base': 'http://127.0.0.1:16876',
        'api_token': 'tasknotes-token',
        'vault_root': Path('/tmp/unused-vault'),
        'dry_run': True,
        'limit': None,
        'include_deleted': False,
        'include_completed': True,
        'stop_on_error': False,
        'subtasks_mode': 'native-project-link',
        'report': report_path,
    }
    base.update(overrides)
    return base


class TestMigrationDryRun(unittest.TestCase):
    def _run_migrate(self, args: migrator.Args) -> tuple[int, str]:
        buffer = io.StringIO()
        with patch('migrate_todoist_to_tasknotes.api_request', side_effect=AssertionError('api_request must not be called in dry-run')):
            with patch(
                'migrate_todoist_to_tasknotes.build_todoist_id_cache',
                side_effect=AssertionError('build_todoist_id_cache must not be called in dry-run'),
            ):
                with redirect_stdout(buffer):
                    exit_code = migrator.migrate(args)
        return exit_code, buffer.getvalue()

    def test_dry_run_prints_payload_json_without_api_calls(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            report_path = Path(tmp_dir) / 'report.md'
            exit_code, output = self._run_migrate(_dry_run_args(report_path))

        self.assertEqual(exit_code, 0)
        self.assertIn('DRY-RUN create: 100', output)
        self.assertIn('"title": "Parent task"', output)
        payload = _extract_dry_run_payload(output, '100')
        self.assertEqual(payload['title'], 'Parent task')

    def test_deleted_items_skipped_by_default(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            report_path = Path(tmp_dir) / 'report.md'
            _, output = self._run_migrate(_dry_run_args(report_path))

        self.assertIn('SKIP deleted: 103', output)
        self.assertNotIn('DRY-RUN create: 103', output)

    def test_completed_items_included_by_default(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            report_path = Path(tmp_dir) / 'report.md'
            _, output = self._run_migrate(_dry_run_args(report_path))

        self.assertIn('DRY-RUN create: 102', output)
        self.assertNotIn('SKIP completed: 102', output)

    def test_completed_items_skipped_when_disabled(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            report_path = Path(tmp_dir) / 'report.md'
            _, output = self._run_migrate(
                _dry_run_args(report_path, include_completed=False),
            )

        self.assertIn('SKIP completed: 102', output)
        self.assertNotIn('DRY-RUN create: 102', output)

    def test_parent_processed_before_child(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            report_path = Path(tmp_dir) / 'report.md'
            _, output = self._run_migrate(_dry_run_args(report_path))

        parent_pos = output.index('DRY-RUN create: 100')
        child_pos = output.index('DRY-RUN create: 101')
        self.assertLess(parent_pos, child_pos)

    def test_dry_run_writes_report_with_summary(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            report_path = Path(tmp_dir) / 'migration_run_report.md'
            self._run_migrate(_dry_run_args(report_path))

            content = report_path.read_text(encoding='utf-8')
            self.assertTrue(report_path.is_file())
            self.assertIn('## Summary', content)
            self.assertIn('- skipped_deleted: 1', content)
            self.assertIn('- created:', content)


if __name__ == '__main__':
    unittest.main()
