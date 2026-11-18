"""Read existing local installations without moving or duplicating their data."""

import os


def load_legacy_environment():
    for name, value in list(os.environ.items()):
        if name.startswith("LINDE_"):
            os.environ.setdefault("ALGYRE_" + name[6:], value)


def local_database(data_dir):
    current = data_dir / "algyre.sqlite"
    previous = data_dir / "linde.sqlite"
    return previous if previous.is_file() and not current.exists() else current
