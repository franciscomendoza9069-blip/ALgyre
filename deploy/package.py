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
        "tenancy.py",
        "manage.py",
        "import_workflow.py",
        "schema.sql",
        "requirements-lock.txt",
        "requirements.txt",
        ".env.example",
        "README.md",
        "LICENSE",
        "NOTICE",
        "CHANGELOG.md",
        "Abrir ALgyre.cmd",
        "Cerrar ALgyre.cmd",
        "abrir-algyre.ps1",
        "cerrar-algyre.ps1",
    ]:
        archive.add(root / name, arcname=name)
    for folder in ["static", "deploy", "tests", "algyre_core", "docs"]:
        for path in sorted((root / folder).glob("*")):
            if path.is_file() and path.suffix not in {".pyc", ".gz"}:
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
