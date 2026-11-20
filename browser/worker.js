import {loadPyodide} from "/pyodide.mjs";

async function readAsset(name) {
  const result = await fetch(name);
  if (!result.ok) throw new Error("Missing execution asset");
  return result.text();
}

try {
  const [python, runner, checker] = await Promise.all([
    loadPyodide({indexURL: new URL("/", location.href).href, jsglobals: Object.freeze(Object.create(null))}),
    readAsset("/runner.py"),
    readAsset("/checker.py"),
  ]);
  python.FS.writeFile("/home/pyodide/runner.py", runner);
  python.FS.writeFile("/home/pyodide/checker.py", checker);
  const execute = python.runPython(`
import json
import runner
import checker

def execute(payload):
    data = json.loads(payload)
    if data.get("check") is not None:
        result = checker.evaluate(data["check"], data["code"], data["stdin"])
    else:
        result = runner.run_code(data["code"], data["stdin"])
    return json.dumps(result)
execute
`);
  addEventListener("message", ({data}) => {
    try {
      postMessage({result: JSON.parse(execute(JSON.stringify(data)))});
    } catch {
      postMessage({result: {error: "Python could not finish this run. Try again."}});
    } finally {
      execute.destroy();
    }
  }, {once: true});
  postMessage({ready: true});
} catch {
  postMessage({result: {error: "The bundled Python runtime could not load."}});
}
