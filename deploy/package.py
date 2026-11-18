"""Build the deployment bundle from an explicit allowlist; exclude all actual data/secrets."""

import tarfile
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / "work/algyre-publica.tar.gz"
target.parent.mkdir(exist_ok=True)
with tarfile.open(target, "w:gz") as archive:
    for name in [
        "app.py",
        "manage.py",
        "requirements-lock.txt",
        "requirements.txt",
        ".env.example",
        "README.md",
        "README.es.md",
        "LICENSE",
        "NOTICE",
        "CHANGELOG.md",
        "Abrir ALgyre.cmd",
        "Cerrar ALgyre.cmd",
    ]:
        archive.add(root / name, arcname=name)
    source_suffixes = {
        ".py",
        ".sql",
        ".js",
        ".cjs",
        ".css",
        ".html",
        ".svg",
        ".jpg",
        ".png",
        ".md",
        ".sh",
        ".ps1",
        ".service",
        ".timer",
    }
    for folder in ["static", "deploy", "tests", "algyre_core", "docs", "scripts"]:
        for path in sorted((root / folder).rglob("*")):
            if (
                path.is_file()
                and path.suffix in source_suffixes
                and "__pycache__" not in path.parts
            ):
                archive.add(path, arcname=path.relative_to(root))
print(target)

# A ZIP is convenient for people installing on their own computer.
local_target = root / "work/algyre-descarga.zip"
with tarfile.open(target, "r:gz") as source:
    with zipfile.ZipFile(local_target, "w", zipfile.ZIP_DEFLATED) as archive:
        for member in source.getmembers():
            if member.isfile():
                with source.extractfile(member) as content:
                    archive.writestr("algyre/" + member.name, content.read())
print(local_target)
