"""A string read from storage into chat keeps its quote marks ("talice") unless the text says interpret."""
import re

import datapacks

STRINGS = ["held.vault.name", "name", "status", "target.name", "label", "contest.month", "contest.theme",
           "contest.about"]


def test_strings_read_from_storage_are_interpreted():
    text = "\n".join(v for k, v in datapacks.all_files().items() if k.endswith(".mcfunction"))
    for path in STRINGS:
        found = re.findall(r'\{[^{}]*"nbt":"' + re.escape(path) + r'"[^{}]*\}', text)
        assert found, path
        assert all('"interpret":true' in one for one in found), path
