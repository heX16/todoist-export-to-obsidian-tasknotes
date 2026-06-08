#!/usr/bin/env python3
"""Obsidian project note and wiki-link helpers for Todoist migration."""

from __future__ import annotations

from pathlib import Path


def sanitize_obsidian_note_name(name: str) -> str:
    """Sanitize a project name for use as an Obsidian note filename."""
    return name.strip().replace('/', '／').replace('\\', '＼')


def project_wikilink(project_name: str) -> str:
    """Return an Obsidian wiki-link target for the given project name."""
    safe_name = sanitize_obsidian_note_name(project_name)
    link_target = safe_name[:-3] if safe_name.lower().endswith('.md') else safe_name
    return f'[[{link_target}]]'


def parent_project_link(parent_task_path: str) -> str:
    """Return an Obsidian wiki-link to a parent task note."""
    return f'[[{Path(parent_task_path).stem}]]'


def project_note_path(vault_root: Path, project_name: str) -> Path:
    """
    Return the expected Obsidian project note path in the vault root.

    Obsidian note names cannot contain path separators. Replace them to avoid
    accidentally creating nested paths.
    """
    safe_name = sanitize_obsidian_note_name(project_name)
    if safe_name.lower().endswith('.md'):
        return vault_root / safe_name
    return vault_root / f'{safe_name}.md'


def ensure_project_note_exists(vault_root: Path, project_name: str) -> Path | None:
    """
    Ensure an Obsidian root-level note exists for the given project.

    This intentionally bypasses the TaskNotes HTTP API and writes directly into
    the vault.
    """
    if not project_name or not project_name.strip():
        return None
    if not vault_root.exists() or not vault_root.is_dir():
        raise RuntimeError(f'Vault root directory does not exist: {vault_root}')

    path = project_note_path(vault_root, project_name)
    if path.exists():
        return path

    path.write_text('\n', encoding='utf-8')
    return path
