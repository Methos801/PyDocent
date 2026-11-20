"""Stage only the browser runtime files listed in the static asset server."""
import hashlib
import io
from pathlib import Path
import tarfile
import urllib.request

from browser_runner import RUNTIME_FILES

VERSION = "314.0.8"
DIGEST = "9a52704e0ae5b07aaacb8e4fed9f1658e8024694a078695ea45ac79dee4cefcb"

def stage():
    url = f"https://registry.npmjs.org/pyodide/-/pyodide-{VERSION}.tgz"
    with urllib.request.urlopen(url, timeout=60) as response:
        data = response.read(20 * 1024 * 1024)
    if hashlib.sha256(data).hexdigest() != DIGEST:
        raise RuntimeError("Browser runtime archive hash mismatch")
    directory = Path(__file__).resolve().parent / "wasm"
    directory.mkdir(exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        for name in RUNTIME_FILES:
            entry = archive.getmember("package/" + name)
            if not entry.isfile():
                raise RuntimeError(f"Invalid browser runtime entry: {name}")
            with archive.extractfile(entry) as source:
                (directory / name).write_bytes(source.read())

if __name__ == "__main__":
    stage()
