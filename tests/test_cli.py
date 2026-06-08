"""CLI parsing tests for migrate_todoist_to_tasknotes."""

from __future__ import annotations

import unittest

import testdata  # noqa: F401

import migrate_todoist_to_tasknotes as migrator


class TestParseArgs(unittest.TestCase):
    def test_help_exits_with_zero(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            migrator.parse_args(['--help'])
        self.assertIn(ctx.exception.code, (0, None))

    def test_limit_parses_integer(self) -> None:
        args = migrator.parse_args(['--limit=5'])
        self.assertEqual(args['limit'], 5)

    def test_limit_rejects_non_integer(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            migrator.parse_args(['--limit=abc'])
        self.assertIn('ERROR: --limit must be an integer', str(ctx.exception))

    def test_include_completed_true_by_default(self) -> None:
        args = migrator.parse_args([])
        self.assertTrue(args['include_completed'])

    def test_no_include_completed_overrides_default(self) -> None:
        args = migrator.parse_args(['--no-include-completed'])
        self.assertFalse(args['include_completed'])

    def test_subtasks_mode_accepts_known_values(self) -> None:
        args = migrator.parse_args(['--subtasks-mode=metadata-only'])
        self.assertEqual(args['subtasks_mode'], 'metadata-only')

    def test_subtasks_mode_rejects_unknown_values(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            migrator.parse_args(['--subtasks-mode=invalid-mode'])
        self.assertIn('ERROR: --subtasks-mode must be one of:', str(ctx.exception))


if __name__ == '__main__':
    unittest.main()
