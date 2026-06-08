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

    def test_include_deleted_false_by_default(self) -> None:
        args = migrator.parse_args(['--api-token=test-token'])
        self.assertFalse(args['include_deleted'])

    def test_include_deleted_one_includes(self) -> None:
        args = migrator.parse_args(['--api-token=test-token', '--include-deleted=1'])
        self.assertTrue(args['include_deleted'])

    def test_include_deleted_parses_truthy_values(self) -> None:
        for value in ('1', 'true', 'yes'):
            with self.subTest(value=value):
                args = migrator.parse_args([f'--api-token=test-token', f'--include-deleted={value}'])
                self.assertTrue(args['include_deleted'])

    def test_include_completed_true_by_default(self) -> None:
        args = migrator.parse_args(['--api-token=test-token'])
        self.assertTrue(args['include_completed'])

    def test_include_completed_zero_excludes(self) -> None:
        args = migrator.parse_args(['--api-token=test-token', '--include-completed=0'])
        self.assertFalse(args['include_completed'])

    def test_include_completed_parses_truthy_values(self) -> None:
        for value in ('1', 'true', 'yes'):
            with self.subTest(value=value):
                args = migrator.parse_args([f'--api-token=test-token', f'--include-completed={value}'])
                self.assertTrue(args['include_completed'])

    def test_configure_obsidian_without_api_token(self) -> None:
        args = migrator.parse_args(['--configure-obsidian=1'])
        self.assertTrue(args['configure_obsidian'])
        self.assertIsNone(args['api_token'])

    def test_configure_obsidian_false_requires_api_token(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            migrator.parse_args(['--configure-obsidian=0'])
        self.assertIn('ERROR: --api-token is required', str(ctx.exception))

    def test_configure_obsidian_parses_truthy_values(self) -> None:
        for value in ('1', 'true', 'yes'):
            with self.subTest(value=value):
                args = migrator.parse_args([f'--configure-obsidian={value}'])
                self.assertTrue(args['configure_obsidian'])


if __name__ == '__main__':
    unittest.main()
