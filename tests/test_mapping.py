"""Payload mapping tests for todoist_tasknotes_mapping."""

from __future__ import annotations

import unittest

import testdata  # noqa: F401
from testdata import MINIMAL_FIXTURE_PATH

from todoist_tasknotes_mapping import (
    build_details,
    build_indexes,
    build_payload,
    load_json,
)


class TestPayloadMapping(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        data = load_json(MINIMAL_FIXTURE_PATH)
        cls.indexes = build_indexes(data)
        cls.items_by_id = cls.indexes['items']

    def test_item_100_payload_fields(self) -> None:
        item = self.items_by_id['100']
        payload = build_payload(item, self.indexes)

        self.assertEqual(payload['title'], 'Parent task')
        self.assertEqual(payload['status'], 'open')
        self.assertEqual(payload['priority'], 'normal')
        self.assertEqual(payload['scheduled'], '')
        self.assertEqual(payload['due'], '2026-06-10')
        self.assertEqual(payload['tags'], ['tag1'])
        self.assertEqual(payload['projects'], ['[[Work／Project]]'])
        self.assertEqual(payload['timeEstimate'], 120)
        self.assertEqual(payload['todoist_id'], '100')
        self.assertEqual(payload['customProperties'], {'todoist_id': '100'})

    def test_item_100_details_include_todoist_notes(self) -> None:
        item = self.items_by_id['100']
        details = build_details(item, self.indexes)

        self.assertIn('Parent description', details)
        self.assertIn('## Todoist notes', details)
        self.assertIn('A note for the parent task', details)

    def test_item_101_subtask_includes_only_parent_wikilink(self) -> None:
        item = self.items_by_id['101']
        payload = build_payload(
            item,
            self.indexes,
            parent_task_path='Tasks/Parent task.md',
        )

        self.assertEqual(payload['projects'], ['[[Parent task]]'])
        self.assertEqual(payload['scheduled'], '')

    def test_item_101_subtask_omits_projects_when_parent_unknown(self) -> None:
        item = self.items_by_id['101']
        payload = build_payload(item, self.indexes)

        self.assertNotIn('projects', payload)
        self.assertEqual(payload['scheduled'], '')


if __name__ == '__main__':
    unittest.main()
