"""Execution helpers loaded by the disposable WebAssembly worker."""
import contextlib
import io
import sys
import traceback

MAX_OUTPUT_CHARS = 4000


class CappedText(io.StringIO):
    def write(self, text):
        room = MAX_OUTPUT_CHARS - self.tell()
        super().write(text[:max(room, 0)])
        if len(text) > room and room >= 0:
            super().write("\n...[output truncated]")
        return len(text)


def run_code(code, stdin_data=""):
    stdout, stderr = CappedText(), CappedText()
    previous_stdin = sys.stdin
    exit_code = 0
    try:
        sys.stdin = io.StringIO(stdin_data)
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                exec(compile(code, "<your code>", "exec"), {"__name__": "__main__"})
            except SystemExit as exc:
                exit_code = 0 if exc.code in (None, 0) else 1
            except BaseException as exc:
                exit_code = 1
                traceback.print_exception(type(exc), exc, exc.__traceback__.tb_next, file=stderr)
                if isinstance(exc, EOFError):
                    print("Add an answer per line in Program input, then try again.", file=stderr)
    finally:
        sys.stdin = previous_stdin
    return {"stdout": stdout.getvalue(), "stderr": stderr.getvalue(),
            "timed_out": False, "exit_code": exit_code}
