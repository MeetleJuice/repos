"""Conservative static checks for the generated-app contract; never execute source."""
import ast
from pathlib import Path


def inspect_files(files, complete=True):
    issues, trees = [], {}
    for name, text in files.items():
        if not name.endswith(".py"):
            continue
        try:
            tree = ast.parse(text, filename=name)
            trees[name] = tree
        except (SyntaxError, ValueError) as exc:
            issues.append(f"{name}: Python syntax error: {exc}")
            continue
        if any(isinstance(node, ast.Import) and any(alias.name in {"cgi", "cgitb"} for alias in node.names) or isinstance(node, ast.ImportFrom) and node.module in {"cgi", "cgitb"} for node in ast.walk(tree)):
            issues.append(f"{name}: Replace cgi/cgitb imports; these modules are unavailable on newer supported Python versions. Parse headers with email.message or string operations.")
    if not complete:
        return {"passed": not issues, "issues": issues, "executed": False}
    if "app.py" not in files:
        issues.append("Missing app.py.")
    elif "app.py" in trees and not any(isinstance(n, ast.FunctionDef) and n.name == "create_server" for n in trees["app.py"].body):
        issues.append("app.py must define create_server(host, port).")
    tests = [name for name in files if Path(name).name.startswith("test_") and name.endswith(".py")]
    if not tests:
        issues.append("Missing unittest test file (for example test_app.py). Add tests of the approved features.")
    methods = 0
    for name in tests:
        tree = trees.get(name)
        if tree is None:
            continue
        nodes = list(ast.walk(tree))
        test_methods = [n for n in nodes if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]
        methods += len(test_methods)
        if not test_methods:
            continue  # Support helper-only test modules when another module has tests.
        imports_app = any(isinstance(n, ast.Import) and any(a.name == "app" or a.name.startswith("app.") for a in n.names) or isinstance(n, ast.ImportFrom) and n.module == "app" for n in nodes)
        dynamic_app = any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in {"spec_from_file_location", "import_module"} for n in nodes) and any(isinstance(n, ast.Constant) and n.value in {"app.py", "app"} for n in nodes)
        if not (imports_app or dynamic_app):
            issues.append(f"{name}: Tests must import the real app.py instead of duplicating its server. Use from app import create_server, or import app.")
        if any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "handle_request" for n in nodes):
            issues.append(f"{name}: Do not call server.handle_request() as a response. Start serve_forever in a thread and send real urllib HTTP requests with timeouts.")
        if any(isinstance(n, ast.FunctionDef) and n.name in {"create_server", "do_GET", "do_POST", "do_DELETE"} for n in nodes):
            issues.append(f"{name}: Do not reimplement the application server in its tests. Exercise the imported application.")
    if tests and not methods:
        issues.append("Test files must contain real test_ methods; empty test files are insufficient.")
    return {"passed": not issues, "issues": issues, "executed": False}
