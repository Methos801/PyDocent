"""Preserve learner data outside the repository before updates or branch changes."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
import uuid


def backup():
    root = Path(__file__).resolve().parent
    destination = root.parent / 'PythonTutor-backups' / (datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8])
    destination.mkdir(parents=True)
    manifest = []
    for source in root.rglob('*'):
        if not source.is_file() or '.git' in source.parts or source.is_symlink():
            continue
        is_progress = source.name == 'progress.json'
        is_recovery_copy = source.name.startswith('progress.json.') and source.name.endswith('.corrupt')
        if not (is_progress or is_recovery_copy):
            continue
        relative = source.relative_to(root)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        manifest.append({'path': str(relative), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(f'Backed up {len(manifest)} local data files to {destination}')
    print(f'Root progress.json present: {(root / "progress.json").exists()}')
    return destination


if __name__ == '__main__':
    backup()
