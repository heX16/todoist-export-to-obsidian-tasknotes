"""Tests for TaskNotes Obsidian data.json configuration helpers."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import testdata  # noqa: F401

from tasknotes_obsidian_config import (
    TODOIST_ID_FIELD_KEY,
    apply_tasknotes_obsidian_config,
    load_api_auth_token,
    parse_api_port,
    tasknotes_data_json_path,
)


class TestParseApiPort(unittest.TestCase):
    def test_default_http_port(self) -> None:
        self.assertEqual(parse_api_port('http://127.0.0.1:8080'), 8080)

    def test_explicit_port(self) -> None:
        self.assertEqual(parse_api_port('http://127.0.0.1:16876'), 16876)

    def test_https_default_port(self) -> None:
        self.assertEqual(parse_api_port('https://127.0.0.1'), 443)


class TestApplyTasknotesObsidianConfig(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.vault_root = Path(self.temp_dir.name)
        self.data_json_path = tasknotes_data_json_path(self.vault_root)
        self.data_json_path.parent.mkdir(parents=True)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _write_data(self, data: dict) -> None:
        self.data_json_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + '\n',
            encoding='utf-8',
        )

    def _read_data(self) -> dict:
        with self.data_json_path.open(encoding='utf-8') as handle:
            return json.load(handle)

    def test_applies_user_field_api_token_and_port(self) -> None:
        self._write_data({
            'enableAPI': False,
            'apiPort': 16876,
            'apiAuthToken': 'old-token',
            'userFields': [],
        })

        report = apply_tasknotes_obsidian_config(
            self.vault_root,
            api_token='new-token',
            api_base='http://127.0.0.1:8080',
        )

        self.assertTrue(report['added_user_field'])
        self.assertTrue(report['enabled_api'])
        self.assertTrue(report['updated_token'])
        self.assertTrue(report['updated_port'])
        self.assertFalse(report['unchanged'])

        data = self._read_data()
        self.assertTrue(data['enableAPI'])
        self.assertEqual(data['apiPort'], 8080)
        self.assertEqual(data['apiAuthToken'], 'new-token')
        self.assertEqual(len(data['userFields']), 1)
        self.assertEqual(data['userFields'][0]['key'], TODOIST_ID_FIELD_KEY)
        self.assertTrue(self.data_json_path.with_suffix('.json.bak').is_file())

    def test_idempotent_second_run(self) -> None:
        self._write_data({
            'enableAPI': False,
            'apiPort': 8080,
            'apiAuthToken': 'token',
            'userFields': [],
        })

        apply_tasknotes_obsidian_config(
            self.vault_root,
            api_token='token',
            api_base='http://127.0.0.1:8080',
        )
        report = apply_tasknotes_obsidian_config(
            self.vault_root,
            api_token='token',
            api_base='http://127.0.0.1:8080',
        )

        self.assertTrue(report['unchanged'])
        data = self._read_data()
        todoist_fields = [
            field for field in data['userFields']
            if field.get('key') == TODOIST_ID_FIELD_KEY
        ]
        self.assertEqual(len(todoist_fields), 1)

    def test_setup_only_preserves_existing_token(self) -> None:
        self._write_data({
            'enableAPI': False,
            'apiPort': 8080,
            'apiAuthToken': 'keep-me',
            'userFields': [],
        })

        report = apply_tasknotes_obsidian_config(
            self.vault_root,
            api_token=None,
            api_base='http://127.0.0.1:8080',
        )

        self.assertFalse(report['updated_token'])
        data = self._read_data()
        self.assertEqual(data['apiAuthToken'], 'keep-me')

    def test_missing_data_json_exits(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            apply_tasknotes_obsidian_config(
                self.vault_root,
                api_token='token',
            )
        self.assertIn('data.json not found', str(ctx.exception))

    def test_missing_vault_root_exits(self) -> None:
        missing = self.vault_root / 'missing'
        with self.assertRaises(SystemExit) as ctx:
            apply_tasknotes_obsidian_config(
                missing,
                api_token='token',
            )
        self.assertIn('Vault root directory does not exist', str(ctx.exception))

    def test_load_api_auth_token_reads_config(self) -> None:
        self._write_data({'apiAuthToken': 'from-config'})

        self.assertEqual(load_api_auth_token(self.vault_root), 'from-config')

    def test_load_api_auth_token_returns_none_when_missing(self) -> None:
        self._write_data({'enableAPI': True})

        self.assertIsNone(load_api_auth_token(self.vault_root))


if __name__ == '__main__':
    unittest.main()
