# Third-party notices

The MIT license covers PyDocent's original code and lessons.

- **CodeMirror 5.65.16**, including Python mode and the Dracula theme, is included under the [MIT license](licenses/CodeMirror-MIT.txt). [Upstream source](https://github.com/codemirror/codemirror5/tree/5.65.16).
- The runtime setup downloads **Pyodide 314.0.8** from the upstream npm registry and verifies the pinned archive digest. It uses five files from the archive, including browser CPython and Emscripten output. See the [Pyodide license and corresponding source](https://github.com/pyodide/pyodide/tree/314.0.8), [CPython source](https://github.com/python/cpython/tree/v3.14.2), and [Emscripten source](https://github.com/emscripten-core/emscripten/tree/5.0.3). Related notices are retained under `licenses/runtime/`.
- The browser CPython source includes [HACL* MIT notices](licenses/runtime/HACL-CPython-3.14.2-MIT.txt).
- The local server imports separately installed packages listed in `requirements.txt`. The installed packages include their own license files.

This source preview uses system fonts. The browser runtime, Python environment, and Windows binaries are downloaded or installed separately from the preview ZIP.
