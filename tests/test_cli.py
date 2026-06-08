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
        args = migrator.parse_args(['--api-token=test-token', '--limit=5'])
        self.assertEqual(args['limit'], 5)

    def test_limit_rejects_non_integer(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            migrator.parse_args(['--api-token=test-token', '--limit=abc'])
        self.assertIn('ERROR: --limit must be an integer', str(ctx.exception))

    def test_api_token_is_required(self) -> None:
        with self.assertRaises(SystemExit):
            migrator.parse_args([])

    def test_include_completed_true_by_default(self) -> None:
        args = migrator.parse_args(['--api-token=test-token'])
        self.assertTrue(args['include_completed'])

    def test_no_include_completed_overrides_default(self) -> None:
        args = migrator.parse_args(['--api-token=test-token', '--no-include-completed'])
        self.assertFalse(args['include_completed'])


if __name__ == '__main__':
    unittest.main()
