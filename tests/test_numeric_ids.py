"""Regression tests for numeric Todoist id fields."""

from __future__ import annotations

import unittest

import testdata  # noqa: F401
from testdata import NUMERIC_IDS_FIXTURE_PATH

from todoist_tasknotes_mapping import (
    build_details,
    build_indexes,
    build_payload,
    compute_creation_order,
    load_json,
)


def _item_by_id(items_by_id: dict, item_id: str) -> dict:
    for item in items_by_id.values():
        if str(item['id']) == item_id:
            return item
    raise KeyError(item_id)


class TestNumericTodoistIds(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        data = load_json(NUMERIC_IDS_FIXTURE_PATH)
        cls.indexes = build_indexes(data)
        cls.items_by_id = cls.indexes['items']

    def test_indexes_use_string_keys(self) -> None:
        self.assertIn('100', self.items_by_id)
        self.assertIn('200', self.indexes['projects'])

    def test_notes_are_indexed_by_string_item_id(self) -> None:
        notes = self.indexes['notes_by_item_id'].get('100', [])
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]['content'], 'A note for the parent task')

    def test_parent_first_order_with_numeric_ids(self) -> None:
        ordered = compute_creation_order(list(self.items_by_id.values()))
        ordered_ids = [str(item['id']) for item in ordered]
        self.assertLess(ordered_ids.index('100'), ordered_ids.index('101'))

    def test_payload_uses_string_todoist_id(self) -> None:
        item = _item_by_id(self.items_by_id, '100')
        payload = build_payload(item, self.indexes, subtasks_mode='native-project-link')

        self.assertEqual(payload['todoist_id'], '100')
        self.assertEqual(payload['customProperties'], {'todoist_id': '100'})
        self.assertIn('## Todoist notes', build_details(item, self.indexes))


if __name__ == '__main__':
    unittest.main()
