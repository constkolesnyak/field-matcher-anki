from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from aqt import gui_hooks, mw
from aqt.qt import (
    QAction,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from aqt.utils import showInfo, tooltip


class MatchMode(StrEnum):
    EQUAL = 'equal'
    UNEQUAL = 'unequal'

    @property
    def label(self) -> str:
        return 'Equal' if self is MatchMode.EQUAL else 'Unequal'


CONFIG_PATH = Path(__file__).with_name('config.json')


@dataclass
class Config:
    field1_name: str = ''
    field2_name: str = ''
    filter: str = ''
    match_mode: MatchMode = MatchMode.UNEQUAL
    tag_name: str = 'field-matcher'

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> 'Config':
        defaults = cls()

        def _as_str(value: Any, default: str = '') -> str:
            if value in (None,):
                return default
            return str(value)

        match_mode_raw = data.get('match_mode', defaults.match_mode)
        try:
            match_mode = MatchMode(match_mode_raw)
        except ValueError:
            match_mode = MatchMode.UNEQUAL

        return cls(
            field1_name=_as_str(data.get('field1_name', defaults.field1_name), defaults.field1_name),
            field2_name=_as_str(data.get('field2_name', defaults.field2_name), defaults.field2_name),
            filter=_as_str(data.get('filter', defaults.filter), defaults.filter),
            match_mode=match_mode,
            tag_name=_as_str(data.get('tag_name', defaults.tag_name), defaults.tag_name) or defaults.tag_name,
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            'field1_name': self.field1_name,
            'field2_name': self.field2_name,
            'filter': self.filter,
            'match_mode': self.match_mode,
            'tag_name': self.tag_name,
        }


def load_config() -> Config:
    if CONFIG_PATH.exists():
        try:
            with CONFIG_PATH.open('r', encoding='utf-8') as handle:
                raw = json.load(handle)
            if isinstance(raw, Mapping):
                return Config.from_mapping(raw)
        except (OSError, ValueError, TypeError) as err:
            tooltip(f'Field Matcher: using defaults because config is invalid ({err}).')
    return Config()


def save_config(config: Config) -> None:
    try:
        with CONFIG_PATH.open('w', encoding='utf-8') as handle:
            json.dump(config.to_mapping(), handle, indent=2)
            handle.write('\n')
    except OSError as err:
        showInfo(f'Field Matcher: failed to save config ({err}).')


def anki_field_matcher() -> None:
    if not mw.col:
        showInfo('No collection loaded.')
        return

    config = load_config()
    updated_config = request_config_from_user(config)
    if updated_config is None:
        return

    if not updated_config.field1_name or not updated_config.field2_name:
        showInfo('Both field names must be provided.')
        return

    if not updated_config.tag_name:
        showInfo('Tag must be provided.')
        return

    save_config(updated_config)

    tagged_count, skipped_count = tag_matching_notes(updated_config)

    message = f"Tagged {tagged_count} cards with '{updated_config.tag_name}' tag."
    if skipped_count:
        message += f'\nSkipped {skipped_count} notes without the specified fields.'
    showInfo(message)


def request_config_from_user(config: Config) -> Config | None:
    dialog = QDialog(mw)
    dialog.setWindowTitle('Field Matcher')
    layout = QVBoxLayout(dialog)

    layout.addWidget(QLabel('First field:', dialog))
    field1_input = QLineEdit(config.field1_name, dialog)
    layout.addWidget(field1_input)

    layout.addWidget(QLabel('Second field:', dialog))
    field2_input = QLineEdit(config.field2_name, dialog)
    layout.addWidget(field2_input)

    layout.addWidget(QLabel('Filter (e.g., deck:vocab):', dialog))
    filter_input = QLineEdit(config.filter, dialog)
    layout.addWidget(filter_input)

    layout.addWidget(QLabel('Tag cards where fields are:', dialog))
    match_mode_combo = _build_match_mode_combo(dialog, config.match_mode)
    layout.addWidget(match_mode_combo)

    layout.addWidget(QLabel('Tag:', dialog))
    tag_input = QLineEdit(config.tag_name, dialog)
    layout.addWidget(tag_input)

    button_row = QHBoxLayout()
    ok_button = QPushButton('OK', dialog)
    cancel_button = QPushButton('Cancel', dialog)
    ok_button.clicked.connect(dialog.accept)
    cancel_button.clicked.connect(dialog.reject)
    button_row.addWidget(ok_button)
    button_row.addWidget(cancel_button)
    layout.addLayout(button_row)

    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None

    current_mode = match_mode_combo.currentData()
    match_mode = MatchMode(current_mode) if current_mode else MatchMode.UNEQUAL

    return Config(
        field1_name=field1_input.text().strip(),
        field2_name=field2_input.text().strip(),
        filter=filter_input.text().strip(),
        match_mode=match_mode,
        tag_name=tag_input.text().strip(),
    )


def _build_match_mode_combo(parent: QWidget, current: MatchMode) -> QComboBox:
    combo = QComboBox(parent)
    for mode in MatchMode:
        combo.addItem(mode.label, userData=mode.value)
    index = combo.findData(current.value)
    combo.setCurrentIndex(index if index >= 0 else 0)
    return combo


def tag_matching_notes(config: Config) -> tuple[int, int]:
    tagged_count = 0
    skipped_count = 0

    for note_id in mw.col.find_notes(config.filter):
        note = mw.col.get_note(note_id)
        note_type = note.note_type()
        field_names = {field['name'] for field in note_type['flds']}

        if config.field1_name not in field_names or config.field2_name not in field_names:
            skipped_count += 1
            continue

        field1_value = note[config.field1_name].strip()
        field2_value = note[config.field2_name].strip()

        should_tag = (
            bool(field1_value) and field1_value == field2_value
            if config.match_mode is MatchMode.EQUAL
            else field1_value != field2_value
        )

        if should_tag and config.tag_name not in note.tags:
            note.tags.append(config.tag_name)
            note.flush()
            tagged_count += 1

    return tagged_count, skipped_count


_ACTION_LABEL = 'Match (Un)equal Fields'
_action: QAction | None = None


def add_to_menu() -> None:
    global _action

    if not getattr(mw, 'form', None):
        return

    menu = getattr(mw.form, 'menuTools', None)
    if menu is None:
        return

    if _action and _action in menu.actions():
        menu.removeAction(_action)
        _action.deleteLater()
        _action = None
    else:
        for existing in menu.actions():
            if existing.text() == _ACTION_LABEL:
                menu.removeAction(existing)
                existing.deleteLater()
                break

    _action = QAction(_ACTION_LABEL, mw)
    _action.triggered.connect(anki_field_matcher)
    menu.addAction(_action)


gui_hooks.main_window_did_init.append(add_to_menu)

if getattr(mw, 'form', None):
    add_to_menu()
