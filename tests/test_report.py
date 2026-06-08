"""Report generation tests."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import testdata  # noqa: F401

import migrate_todoist_to_tasknotes as migrator


class TestReportRender(unittest.TestCase):
    def test_human_report_contains_summary_counts(self) -> None:
        stats = migrator.MigrationStats(
            total=4,
            skipped_deleted=1,
            skipped_completed=0,
            skipped_duplicate=0,
            created=3,
            failed=0,
        )

        report = migrator.build_report_data(
            stats=stats,
            dry_run=True,
            limit=None,
            subtasks_mode='native-project-link',
            json_path=Path('tests/todoist_minimal.json'),
            api_base='http://127.0.0.1:16876',
        )
        content = migrator.render_report_human(report)

        self.assertIn('## Summary', content)
        self.assertIn('- total: 4', content)
        self.assertIn('- skipped_deleted: 1', content)
        self.assertIn('- skipped_completed: 0', content)
        self.assertIn('- created: 3', content)
        self.assertIn('- failed: 0', content)

    def test_json_report_is_valid_json(self) -> None:
        stats = migrator.MigrationStats(total=1, created=1)

        report = migrator.build_report_data(
            stats=stats,
            dry_run=True,
            limit=None,
            subtasks_mode='native-project-link',
            json_path=Path('tests/todoist_minimal.json'),
            api_base='http://127.0.0.1:16876',
        )
        json_text = migrator.render_report_json(report)
        parsed = json.loads(json_text)
        self.assertEqual(parsed['summary']['created'], 1)


if __name__ == '__main__':
    unittest.main()
