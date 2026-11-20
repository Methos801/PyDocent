"""Challenge checks executed in the browser Worker.

The old design only looked at program output on the client side (e.g. "did
anything print?"), so almost anything passed. Checks run inside the execution Worker and are lesson-specific behavioral tests:

- ``no_error``            the program runs cleanly (no traceback, no timeout)
- ``output_contains``     the output contains a value (optionally case-folded)
- ``output_not_contains`` the output does NOT contain a value
- ``output_line_count``   at least ``min`` non-empty output lines
- ``output_lines_in_order`` values appear as output lines, in order
- ``probe``               runs a hidden expression in the learner's namespace
                          (same process, right after their code) and compares
                          the result — e.g. ``len(hobbies) == 3`` or
                          ``double(5) == 10``. This verifies the *behavior*
                          of the learner's variables/functions, not just the
                          text they printed, while still accepting many valid
                          solutions.

Every test carries a learner-facing ``message`` so the Check button can show
exactly which requirements are met and which are not.

Probes print a marker line that is stripped from the output shown to the
learner. A probe that raises (e.g. the variable doesn't exist) is reported as
a failed test with its message — never as a crash.
"""
import ast
import copy
from collections import Counter
import json
import re
import unicodedata

import runner

PROBE_MARKER = "__TUTOR_PROBE__"
PROBE_ERROR = "__TUTOR_PROBE_ERROR__"


def _nonempty_lines(text):
    return [ln for ln in text.splitlines() if ln.strip()]


def _has_named_greeting(text):
    """Check the stated greeting format without guessing the learner's identity."""
    for line in text.splitlines():
        match = re.fullmatch(r"\s*hello\s*,?\s+my\s+name\s+is\s+(.+?)\s*[.!]?\s*", line, re.IGNORECASE)
        if not match:
            continue
        name = match.group(1).strip()
        if any(unicodedata.category(c).startswith('L') for c in name) and all(
            unicodedata.category(c)[0] in ('L', 'M') or c in " -'’" for c in name
        ):
            return True
    return False


def _type_name(value):
    """Map a JSON-decoded probe value to the Python type name learners know."""
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "dict"
    if value is None:
        return "NoneType"
    return type(value).__name__


def _multi_probe_trailer(exprs):
    """Append code that evaluates several probe expressions at once."""
    lines = ["\nimport json as __tutor_json", "__tutor_values__ = []"]
    for i, expr in enumerate(exprs):
        lines.extend(["try:", f"    __tutor_values__.append({expr})", "except BaseException:", "    __tutor_values__.append('__failed__')"])
    lines.append(
        "print('\\n" + PROBE_MARKER + "' + __tutor_json.dumps(__tutor_values__))"
    )
    return "\n".join(lines) + "\n"


def _split_multi_probe(stdout):
    """Strip the multi-probe marker line; return (clean_stdout, [values])."""
    clean_lines = []
    values = []
    for line in stdout.splitlines():
        if line.startswith(PROBE_MARKER):
            payload = line[len(PROBE_MARKER):]
            if payload == PROBE_ERROR:
                values = ["__failed__"]
            else:
                try:
                    values = json.loads(payload)
                    if not isinstance(values, list):
                        values = ["__failed__"]
                except json.JSONDecodeError:
                    values = ["__failed__"]
        else:
            clean_lines.append(line)
    return "\n".join(clean_lines), values


def evaluate(check, code, stdin_data=""):
    """Run the learner code and evaluate every test inside the Worker."""
    tests = (check or {}).get("tests") or []
    stdin = (check or {}).get("stdin")
    if stdin is None:
        stdin = stdin_data or ""

    probe_exprs = [t.get("expr", "") for t in tests if t.get("kind") in ("probe", "printed_values")]
    try:
        tree = ast.parse(code)
    except (SyntaxError, RecursionError, ValueError):
        tree = None
    probe_code = code
    if probe_exprs:
        probe_code = code + _multi_probe_trailer(probe_exprs)

    res = runner.run_code(probe_code, stdin_data=stdin)
    stdout, probe_values = res["stdout"], ["__failed__"] * len(probe_exprs)
    if probe_exprs:
        stdout, probe_values = _split_multi_probe(stdout)

    results = []
    probe_idx = 0
    for t in tests:
        kind = t.get("kind")
        message = t.get("message") or "Requirement not met"
        ok = False
        if kind == "no_error":
            ok = (not res["timed_out"]) and res["exit_code"] == 0 and \
                not (res["stderr"] or "").strip()
        elif kind == "named_greeting":
            ok = _has_named_greeting(stdout)
        elif kind == "syntax_feature":
            nodes = list(ast.walk(tree)) if tree else []
            feature = t.get("feature")
            if feature == "for":
                ok = any(isinstance(n, ast.For) for n in nodes)
            elif feature == "for_hobbies":
                ok = any(isinstance(n, ast.For) and isinstance(n.iter, ast.Name) and n.iter.id == 'hobbies' for n in nodes)
            elif feature == "if_else":
                ok = any(isinstance(n, ast.If) and n.orelse for n in nodes)
            elif feature in ("input", "int"):
                ok = any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == feature for n in nodes)
        elif kind == "age_branches" and res['exit_code'] == 0 and not res['timed_out']:
            # Change the top-level starting value and run both sides of the boundary.
            if tree:
                assignments = [i for i, n in enumerate(tree.body) if isinstance(n, ast.Assign)
                               and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name)
                               and n.targets[0].id == 'age']
                if len(assignments) == 1:
                    ok = True
                    for age, expected in ((17, 'you are a minor'), (18, 'you are an adult')):
                        variant = copy.deepcopy(tree)
                        variant.body[assignments[0]].value = ast.Constant(age)
                        trial = runner.run_code(ast.unparse(ast.fix_missing_locations(variant)))
                        if trial['exit_code'] != 0 or trial['timed_out'] or expected not in trial['stdout'].casefold():
                            ok = False
                            break
        elif kind == "input_scenario" and res['exit_code'] == 0 and not res['timed_out']:
            trial = runner.run_code(code, stdin_data=t.get('stdin', ''))
            ok = trial['exit_code'] == 0 and not trial['timed_out'] and all(
                str(value).casefold() in trial['stdout'].casefold() for value in t.get('values', []))
        elif kind == "function_scenario" and res['exit_code'] == 0 and not res['timed_out']:
            trial = runner.run_code(code + _multi_probe_trailer([t['expr']]), stdin_data=t['stdin'])
            trial_output, values = _split_multi_probe(trial['stdout'])
            ok = trial['exit_code'] == 0 and not trial['timed_out'] and len(values) == 1 and isinstance(values[0], str) and bool(values[0].strip()) and values[0] in trial_output
        elif kind == "exact_lines":
            ok = [line.strip().casefold() for line in stdout.splitlines() if line.strip()] == [str(v).casefold() for v in t.get('values', [])]
        elif kind == "output_exact_line":
            ok = str(t.get('value', '')).strip().casefold() in [line.strip().casefold() for line in stdout.splitlines()]
        elif kind == "printed_values":
            value = probe_values[probe_idx] if probe_idx < len(probe_values) else '__failed__'
            probe_idx += 1
            if isinstance(value, list) and value and all(isinstance(v, (str, int)) and not isinstance(v, bool) and str(v).strip() for v in value):
                lines = [line.strip() for line in stdout.splitlines()]
                if t.get('separate_lines'):
                    actual, required = Counter(lines), Counter(str(v) for v in value)
                    ok = all(actual[item] >= count for item, count in required.items())
                else:
                    ok = all(str(v) in stdout for v in value)
        elif kind == "output_contains":
            hay = stdout.lower() if t.get("case") == "fold" else stdout
            needle = str(t.get("value", ""))
            if t.get("case") == "fold":
                needle = needle.lower()
            ok = needle in hay
        elif kind == "output_contains_any":
            # Passes if ANY of the values appears (accepts multiple valid
            # solutions, e.g. either branch of an if/else).
            hay = stdout.lower() if t.get("case") == "fold" else stdout
            ok = any(
                (str(v).lower() if t.get("case") == "fold" else str(v)) in hay
                for v in t.get("values", [])
            )
        elif kind == "output_not_contains":
            hay = stdout.lower() if t.get("case") == "fold" else stdout
            needle = str(t.get("value", ""))
            if t.get("case") == "fold":
                needle = needle.lower()
            ok = needle not in hay
        elif kind == "output_line_count":
            n = len(_nonempty_lines(stdout))
            ok = n >= int(t.get("min", 1)) and n <= int(t.get("max", 10 ** 9))
        elif kind == "output_lines_in_order":
            lines = [ln.strip() for ln in stdout.splitlines()]
            pos = 0
            ok = True
            for want in t.get("values", []):
                found = False
                while pos < len(lines):
                    if str(want).lower() in lines[pos].lower():
                        pos += 1
                        found = True
                        break
                    pos += 1
                if not found:
                    ok = False
                    break
        elif kind == "probe":
            value = probe_values[probe_idx] if probe_idx < len(probe_values) else "__failed__"
            probe_idx += 1
            if value != "__failed__":
                if "equals" in t:
                    ok = value == t["equals"]
                elif "type" in t:
                    ok = _type_name(value) == t["type"]
                elif "contains" in t:
                    # Probe result must be a string containing every value
                    # (accepts many valid phrasings of the same idea).
                    ok = isinstance(value, str) and \
                        all(str(c) in value for c in t["contains"])
        else:
            ok = False  # unknown test kinds fail loudly in dev, softly for kids

        results.append({"ok": bool(ok), "message": message})

    return {
        "passed": bool(results) and all(r["ok"] for r in results),
        "tests": results,
        "stdout": stdout,
        "stderr": res["stderr"],
        "timed_out": res["timed_out"],
        "exit_code": res["exit_code"],
    }
