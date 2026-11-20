"""Read-only, separate loopback origin for browser execution assets."""
from hashlib import sha256
from pathlib import Path
from threading import Thread
from werkzeug.serving import WSGIRequestHandler, make_server
from werkzeug.wrappers import Request, Response

RUNTIME_FILES = (
    "pyodide.mjs", "pyodide.asm.mjs", "pyodide.asm.wasm",
    "pyodide-lock.json", "python_stdlib.zip",
)

class QuietHandler(WSGIRequestHandler):
    def log_request(self, *args, **kwargs):
        pass  # URLs in this origin are untrusted; avoid recording them.

def start_runner(bundle, ui_origin):
    root = Path(bundle)
    assets = {"/" + name: root / "wasm" / name for name in RUNTIME_FILES}
    assets.update({
        "/frame.html": root / "browser" / "frame.html",
        "/frame.js": root / "browser" / "frame.js",
        "/worker.js": root / "browser" / "worker.js",
        "/runner.py": root / "runner.py",
        "/checker.py": root / "checker.py",
    })
    # Load fixed public assets before binding. The request handler does no file I/O.
    types = {".mjs": "text/javascript", ".js": "text/javascript",
             ".html": "text/html", ".wasm": "application/wasm", ".json": "application/json"}
    payloads = {route: (path.read_bytes(), types.get(path.suffix, "application/octet-stream"))
                for route, path in assets.items()}
    runtime_digests = {"/" + name: sha256(payloads["/" + name][0]).hexdigest()
                       for name in RUNTIME_FILES}

    @Request.application
    def serve(req):
        if (req.host != f"127.0.0.1:{server.server_port}" or req.method not in ("GET", "HEAD")
                or req.query_string or req.path not in payloads):
            return Response("Asset unavailable", status=404)
        content, mime = payloads[req.path]
        response = Response(content, mimetype=mime)
        response.headers.update({
            "Content-Security-Policy": (
                "default-src 'none'; script-src 'self' 'wasm-unsafe-eval'; "
                + (f"worker-src 'self'; frame-ancestors {ui_origin}; "
                   if req.path == "/frame.html" else "worker-src 'none'; connect-src 'self'; ")
                + "base-uri 'none'; form-action 'none'"
            ),
            "Referrer-Policy": "no-referrer",
            "Cross-Origin-Resource-Policy": "same-origin" if req.path != "/frame.html" else "cross-origin",
            "X-Content-Type-Options": "nosniff",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=(), clipboard-read=(), clipboard-write=()",
            "Cache-Control": "private, no-cache" if req.path in runtime_digests else "no-store",
        })
        if req.path in runtime_digests:
            response.set_etag(runtime_digests[req.path])
            response.make_conditional(req)
        return response

    server = make_server("127.0.0.1", 0, serve, threaded=True, request_handler=QuietHandler)
    Thread(target=server.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{server.server_port}"
