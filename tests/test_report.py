"""Report generation tests."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import testdata  # noqa: F401

import migrate_todoist_to_tasknotes as migrator


class TestWriteReport(unittest.TestCase):
    def test_report_contains_summary_counts(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            report_path = Path(tmp_dir) / 'nested' / 'migration_report.md'
            stats = migrator.MigrationStats(
                total=4,
                skipped_deleted=1,
                skipped_completed=0,
                skipped_duplicate=0,
                created=3,
                failed=0,
            )
            started_at = datetime(2026, 6, 8, 10, 0, 0, tzinfo=timezone.utc)
            finished_at = datetime(2026, 6, 8, 10, 1, 0, tzinfo=timezone.utc)

            migrator.write_report(
                report_path,
                started_at=started_at,
                finished_at=finished_at,
                stats=stats,
                dry_run=True,
                limit=None,
                subtasks_mode='native-project-link',
                json_path=Path('tests/todoist_minimal.json'),
                api_base='http://127.0.0.1:16876',
            )

            content = report_path.read_text(encoding='utf-8')
            self.assertTrue(report_path.is_file())
            self.assertIn('## Summary', content)
            self.assertIn('- total: 4', content)
            self.assertIn('- skipped_deleted: 1', content)
            self.assertIn('- skipped_completed: 0', content)
            self.assertIn('- created: 3', content)
            self.assertIn('- failed: 0', content)


if __name__ == '__main__':
    unittest.main()
