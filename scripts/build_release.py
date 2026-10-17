"""Create the exact plugin archive expected by MoviePilot's release installer."""
import hashlib
import json
from pathlib import Path
import zipfile

from check_release import ROOT, PID, check


def build():
    """Package only the runtime directory, with ffproberename/ at archive root."""
    check()
    version = json.loads((ROOT / 'package.v3.json').read_text(encoding='utf-8'))[PID]['version']
    source = ROOT / 'plugins.v3' / PID.lower()
    output = ROOT / 'dist'
    output.mkdir(exist_ok=True)
    archive = output / f'{PID.lower()}_v{version}.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(source.rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix not in ('.pyc', '.pyo'):
                zf.write(path, path.relative_to(source.parent).as_posix())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (output / 'SHA256SUMS').write_text(f'{digest}  {archive.name}\n', encoding='utf-8')
    print(archive.name, digest)


if __name__ == '__main__':
    build()
