"""Tests for resolving api token from TaskNotes config in main()."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import testdata  # noqa: F401

import migrate_todoist_to_tasknotes as migrator
from tasknotes_obsidian_config import tasknotes_data_json_path


class TestMainApiTokenResolution(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.vault_root = Path(self.temp_dir.name)
        self.data_json_path = tasknotes_data_json_path(self.vault_root)
        self.data_json_path.parent.mkdir(parents=True)
        self.data_json_path.write_text(
            json.dumps({
                'enableAPI': True,
                'apiPort': 8080,
                'apiAuthToken': 'stored-token',
                'userFields': [],
            }) + '\n',
            encoding='utf-8',
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _base_args(self) -> dict:
        return {
            'json_path': Path('todoist.json'),
            'api_base': 'http://127.0.0.1:8080',
            'api_token': None,
            'vault_root': self.vault_root,
            'change_obsidian_options': True,
            'dry_run': False,
            'limit': None,
            'include_deleted': False,
            'include_completed': True,
            'stop_on_error': False,
            'report_format': 'human',
        }

    def test_change_obsidian_options_uses_token_from_config(self) -> None:
        with patch.object(migrator, 'parse_args', return_value=self._base_args()):
            with patch.object(migrator, 'migrate', return_value=0) as migrate_mock:
                exit_code = migrator.main()

        self.assertEqual(exit_code, 0)
        migrate_mock.assert_called_once()
        self.assertEqual(migrate_mock.call_args.args[0]['api_token'], 'stored-token')

    def test_change_obsidian_options_without_token_exits_after_setup(self) -> None:
        self.data_json_path.write_text(
            json.dumps({'enableAPI': False, 'userFields': []}) + '\n',
            encoding='utf-8',
        )

        with patch.object(migrator, 'parse_args', return_value=self._base_args()):
            with patch.object(migrator, 'migrate') as migrate_mock:
                exit_code = migrator.main()

        self.assertEqual(exit_code, 0)
        migrate_mock.assert_not_called()


if __name__ == '__main__':
    unittest.main()
