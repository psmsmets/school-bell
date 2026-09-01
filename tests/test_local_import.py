from pathlib import Path

import school_bell


def test_school_bell_is_imported_from_local_source_tree():
    repository_root = Path(__file__).resolve().parents[1]
    imported_package = Path(school_bell.__file__).resolve()

    assert imported_package.is_relative_to(repository_root / 'src')
