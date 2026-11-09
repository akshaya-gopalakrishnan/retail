"""Disable Frappe test entry points in the hosted image, never on a live DB.

Run only during Containerfile construction. No site config or environment flag
can enable these functions afterward. This is an accident-prevention boundary,
not a sandbox against an administrator executing arbitrary Python or SQL.
"""

import ast
from pathlib import Path
import sys


MESSAGE = "Automated tests are blocked in Retail hosted images. Use a disposable local test site."
TARGETS = {
    "apps/frappe/frappe/commands/utils.py": ("run_tests", "run_parallel_tests", "run_ui_tests"),
    "apps/frappe/frappe/test_runner.py": ("main",),
    "apps/frappe/frappe/utils/install.py": ("before_tests",),
    "apps/erpnext/erpnext/setup/utils.py": ("before_tests",),
    "apps/hrms/hrms/tests/test_utils.py": ("before_tests",),
}


def blocked_source(source, names):
    tree = ast.parse(source)
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    missing = set(names) - functions.keys()
    if missing:
        raise RuntimeError(f"Hosted test protection targets missing: {sorted(missing)}")
    lines = source.splitlines(keepends=True)
    for node in sorted((functions[name] for name in names), key=lambda node: node.lineno, reverse=True):
        first = node.body[0]
        # Retain function docstrings, including Click's command help.
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
            position = first.end_lineno
            if len(node.body) < 2:
                raise RuntimeError(f"Unexpected empty function: {node.name}")
            body_line = lines[node.body[1].lineno - 1]
        else:
            position = first.lineno - 1
            body_line = lines[first.lineno - 1]
        indent = body_line[:len(body_line) - len(body_line.lstrip())]
        statement = indent + f"raise RuntimeError({MESSAGE!r})\n"
        if lines[position:position + 1] != [statement]:
            lines.insert(position, statement)
    result = "".join(lines)
    compile(result, "<hosted-test-protection>", "exec")
    return result


def install(root):
    # Validate every target before writing any file. Upstream drift fails builds.
    updates = {root / relative: blocked_source((root / relative).read_text(), names)
               for relative, names in TARGETS.items()}
    for path, source in updates.items():
        path.write_text(source)
    print("Hosted test entry points and destructive before_tests hooks blocked.")


if __name__ == "__main__":
    install(Path(sys.argv[1]))
