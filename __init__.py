import json
import os

from aqt import gui_hooks, mw
from aqt.qt import (
    QAction,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)
from aqt.utils import getText, showInfo, tooltip

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")
DEFAULT_CONFIG = {"field1_name": "", "field2_name": "", "tag_name": "matching-fields", "filter": ""}


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return {**DEFAULT_CONFIG, **json.load(f)}
        except:
            pass
    return DEFAULT_CONFIG.copy()


def save_config(config):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        showInfo(f"Failed to save config: {str(e)}")


def tag_cards_with_matching_fields():
    if not mw.col:
        showInfo("No collection loaded.")
        return

    # Load saved config
    config = load_config()

    # Create dialog to get field names
    dialog = QDialog(mw)
    dialog.setWindowTitle("Field Matcher Configuration")
    layout = QVBoxLayout()

    # Field 1 input
    layout.addWidget(QLabel("First field name:"))
    field1_input = QLineEdit(config["field1_name"])
    layout.addWidget(field1_input)

    # Field 2 input
    layout.addWidget(QLabel("Second field name:"))
    field2_input = QLineEdit(config["field2_name"])
    layout.addWidget(field2_input)

    # Tag name input
    layout.addWidget(QLabel("Tag name:"))
    tag_input = QLineEdit(config["tag_name"])
    layout.addWidget(tag_input)

    # Filter input
    layout.addWidget(QLabel("Filter (e.g., deck:語彙):"))
    filter_input = QLineEdit(config["filter"])
    layout.addWidget(filter_input)

    # Buttons
    button_layout = QHBoxLayout()
    ok_button = QPushButton("OK")
    cancel_button = QPushButton("Cancel")
    button_layout.addWidget(ok_button)
    button_layout.addWidget(cancel_button)
    layout.addLayout(button_layout)

    ok_button.clicked.connect(dialog.accept)
    cancel_button.clicked.connect(dialog.reject)

    dialog.setLayout(layout)

    if not dialog.exec():
        return

    field1_name = field1_input.text().strip()
    field2_name = field2_input.text().strip()
    tag_name = tag_input.text().strip() or "matching-fields"
    filter_query = filter_input.text().strip()

    if not field1_name or not field2_name:
        showInfo("Both field names must be provided.")
        return

    # Save config for next time
    new_config = {
        "field1_name": field1_name,
        "field2_name": field2_name,
        "tag_name": tag_name,
        "filter": filter_query,
    }
    save_config(new_config)

    tagged_count = 0
    skipped_count = 0

    # Get all note IDs with optional filter
    note_ids = mw.col.find_notes(filter_query)

    for nid in note_ids:
        note = mw.col.get_note(nid)
        note_type = note.note_type()
        field_names = [field['name'] for field in note_type['flds']]

        # Check if both fields exist in this note type
        if field1_name not in field_names or field2_name not in field_names:
            skipped_count += 1
            continue

        # Get field values
        field1_value = note[field1_name].strip()
        field2_value = note[field2_name].strip()

        # Check if values match
        if field1_value and field1_value == field2_value:
            # Add tag if not already present
            if tag_name not in note.tags:
                note.tags.append(tag_name)
                note.flush()
                tagged_count += 1

    message = f"Tagged {tagged_count} cards with '{tag_name}' tag."
    if skipped_count > 0:
        message += f"\nSkipped {skipped_count} notes without the specified fields."
    showInfo(message)


def add_to_menu():
    action = QAction("Tag Cards with Matching Fields", mw)
    action.triggered.connect(tag_cards_with_matching_fields)
    mw.form.menuTools.addAction(action)


gui_hooks.main_window_did_init.append(add_to_menu)
