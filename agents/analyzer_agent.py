"""Analyzer Agent: enhanced AST-based code analysis for the QA Council.

Uses ast.NodeVisitor to capture rich metadata per function and class,
including call graphs, exception handling, complexity indicators, and
dependency patterns. This data drives the generator agent's mock strategy.
"""
import ast
import os
from pathlib import Path

from utils.config import get_logger
from utils.path_utils import verify_path_exists

logger = get_logger("analyzer")

# ── AST Visitors ─────────────────────────────────────────────────────────


class FunctionAnalyzer(ast.NodeVisitor):
    """Collect rich metadata from a single function/method body."""

    def __init__(self):
        self.calls: list[str] = []
        self.raises: list[str] = []
        self.has_return = False
        self.complexity = {
            "uses_file_io": False,
            "uses_subprocess": False,
            "uses_http": False,
            "uses_os": False,
            "has_try_except": False,
            "has_conditionals": False,
            "has_loops": False,
        }

    # ── visitors ──────────────────────────────────────────────────────

    def visit_Call(self, node: ast.Call):
        name = _call_name(node)
        if name:
            self.calls.append(name)
            self._classify_call(name)
        self.generic_visit(node)

    def visit_Raise(self, node: ast.Raise):
        if node.exc:
            if isinstance(node.exc, ast.Call):
                name = _call_name(node.exc)
                if name:
                    self.raises.append(name)
            elif isinstance(node.exc, ast.Name):
                self.raises.append(node.exc.id)
        self.generic_visit(node)

    def visit_Return(self, node: ast.Return):
        if node.value is not None:
            self.has_return = True
        self.generic_visit(node)

    def visit_Try(self, node: ast.Try):
        self.complexity["has_try_except"] = True
        self.generic_visit(node)

    # Python 3.11+ uses TryStar for try/except*
    visit_TryStar = visit_Try

    def visit_If(self, node: ast.If):
        self.complexity["has_conditionals"] = True
        self.generic_visit(node)

    def visit_For(self, node: ast.For):
        self.complexity["has_loops"] = True
        self.generic_visit(node)

    def visit_While(self, node: ast.While):
        self.complexity["has_loops"] = True
        self.generic_visit(node)

    # ── helpers ───────────────────────────────────────────────────────

    def _classify_call(self, name: str):
        lower = name.lower()
        if any(k in lower for k in ("open", "read_text", "write_text", "read_bytes")):
            self.complexity["uses_file_io"] = True
        if "subprocess" in lower:
            self.complexity["uses_subprocess"] = True
        if any(k in lower for k in ("httpx", "requests", "aiohttp", "urllib")):
            self.complexity["uses_http"] = True
        if any(k in lower for k in ("os.", "path.", "Path")):
            self.complexity["uses_os"] = True


def _call_name(node: ast.Call) -> str | None:
    """Resolve a Call node to a dotted name string."""
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        parts = []
        current = func
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        return ".".join(reversed(parts))
    return None


# ── Top-level module visitor ─────────────────────────────────────────────


class ModuleAnalyzer(ast.NodeVisitor):
    """Walk a module and collect function / class metadata."""

    def __init__(self, module_name: str):
        self.module_name = module_name
        self.functions: list[dict] = []
        self.classes: list[dict] = []
        self.imports: list[str] = []
        self._current_class: str | None = None

    # ── imports ───────────────────────────────────────────────────────

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.imports.append(alias.name)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        module = node.module or ""
        for alias in node.names:
            self.imports.append(f"{module}.{alias.name}")

    # ── functions ─────────────────────────────────────────────────────

    def visit_FunctionDef(self, node: ast.FunctionDef):
        if self._current_class is None:
            self.functions.append(self._analyze_function(node))

    visit_AsyncFunctionDef = visit_FunctionDef

    # ── classes ───────────────────────────────────────────────────────

    def visit_ClassDef(self, node: ast.ClassDef):
        bases = [_name_of(b) for b in node.bases if _name_of(b)]
        methods = []
        class_variables: list[str] = []
        has_init = False
        init_args: list[dict] = []

        self._current_class = node.name
        for item in ast.iter_child_nodes(node):
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                info = self._analyze_function(item)
                methods.append(info)
                if item.name == "__init__":
                    has_init = True
                    init_args = info["args"]
            elif isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        class_variables.append(target.id)
        self._current_class = None

        self.classes.append({
            "name": node.name,
            "bases": bases,
            "has_init": has_init,
            "init_args": init_args,
            "class_variables": class_variables,
            "methods": methods,
            "line": node.lineno,
            "decorators": [_decorator_name(d) for d in node.decorator_list],
            "docstring": ast.get_docstring(node) or "",
        })

    # ── internal helpers ──────────────────────────────────────────────

    def _analyze_function(self, node) -> dict:
        """Build a rich metadata dict for a single function/method."""
        fa = FunctionAnalyzer()
        for child in ast.walk(node):
            fa.visit(child)

        args_info = []
        for arg in node.args.args:
            if arg.arg == "self":
                continue
            default = _find_default(arg, node.args)
            args_info.append({
                "name": arg.arg,
                "annotation": _annotation_str(arg.annotation),
                "default": default,
            })

        return {
            "name": node.name,
            "args": args_info,
            "is_async": isinstance(node, ast.AsyncFunctionDef),
            "line": node.lineno,
            "decorators": [_decorator_name(d) for d in node.decorator_list],
            "docstring": ast.get_docstring(node) or "",
            "calls": fa.calls,
            "raises": fa.raises,
            "has_return": fa.has_return,
            "complexity_indicators": fa.complexity,
        }


# ── small AST helpers ────────────────────────────────────────────────────


def _name_of(node) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        val = _name_of(node.value)
        return f"{val}.{node.attr}" if val else node.attr
    return None


def _decorator_name(node) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return _name_of(node) or ""
    if isinstance(node, ast.Call):
        return _decorator_name(node.func)
    return ""


def _annotation_str(node) -> str | None:
    if node is None:
        return None
    if isinstance(node, ast.Constant):
        return repr(node.value)
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return _name_of(node)
    return ast.dump(node)


def _find_default(arg: ast.arg, arguments: ast.arguments) -> str | None:
    """Try to find the default value for an argument."""
    # positional defaults are right-aligned
    all_args = arguments.args
    defaults = arguments.defaults
    if not defaults:
        return None
    offset = len(all_args) - len(defaults)
    idx = all_args.index(arg)
    if idx >= offset:
        return _constant_repr(defaults[idx - offset])
    return None


def _constant_repr(node) -> str | None:
    if isinstance(node, ast.Constant):
        return repr(node.value)
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.List):
        return "[]"
    if isinstance(node, ast.Dict):
        return "{}"
    return None


# ── Public API ───────────────────────────────────────────────────────────


def analyze_file(filepath: str) -> dict:
    """Analyze a single Python file and return rich metadata.

    Returns:
        Dict with keys: module, functions, classes, imports, error
    """
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
            source = fh.read()
        tree = ast.parse(source, filename=filepath)
    except SyntaxError as exc:
        return {"module": filepath, "functions": [], "classes": [],
                "imports": [], "error": f"SyntaxError: {exc}"}
    except Exception as exc:
        return {"module": filepath, "functions": [], "classes": [],
                "imports": [], "error": str(exc)}

    module_name = Path(filepath).stem
    visitor = ModuleAnalyzer(module_name)
    visitor.visit(tree)

    return {
        "module": module_name,
        "filepath": filepath,
        "functions": visitor.functions,
        "classes": visitor.classes,
        "imports": visitor.imports,
        "error": None,
    }


def analyze_directory(repo_path: str, max_files: int = 50) -> list[dict]:
    """Analyze all Python files in a repository.

    Skips test files, __pycache__, venv, and hidden directories.

    Returns:
        List of per-file analysis dicts.
    """
    results = []
    skip_dirs = {"__pycache__", ".git", "node_modules", "venv", ".venv",
                 "env", ".env", ".tox", ".mypy_cache", ".pytest_cache"}

    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith(".")]
        for fname in sorted(files):
            if not fname.endswith(".py"):
                continue
            if len(results) >= max_files:
                break
            filepath = os.path.join(root, fname)
            results.append(analyze_file(filepath))
        if len(results) >= max_files:
            break

    return results


def format_analysis_report(analyses: list[dict]) -> str:
    """Build a human-readable summary from analysis results."""
    lines: list[str] = []
    total_funcs = 0
    total_classes = 0

    for data in analyses:
        if data.get("error"):
            lines.append(f"\n{data['module']}: PARSE ERROR - {data['error']}")
            continue

        funcs = data.get("functions", [])
        classes = data.get("classes", [])
        if not funcs and not classes:
            continue

        total_funcs += len(funcs)
        total_classes += len(classes)
        lines.append(f"\n--- {data['module']} ---")

        for fn in funcs:
            args_str = ", ".join(a["name"] for a in fn["args"])
            prefix = "async " if fn["is_async"] else ""
            lines.append(f"  {prefix}def {fn['name']}({args_str})")
            cx = fn.get("complexity_indicators", {})
            flags = [k.replace("uses_", "").replace("has_", "")
                     for k, v in cx.items() if v]
            if flags:
                lines.append(f"    complexity: {', '.join(flags)}")

        for cls in classes:
            bases = f"({', '.join(cls['bases'])})" if cls["bases"] else ""
            lines.append(f"  class {cls['name']}{bases}")
            for m in cls.get("methods", []):
                lines.append(f"    def {m['name']}()")

    header = (
        f"Code Analysis Complete\n"
        f"Files analyzed: {len(analyses)}\n"
        f"Functions found: {total_funcs}\n"
        f"Classes found: {total_classes}\n"
    )
    return header + "\n".join(lines)


async def run_analysis(repo_path: str = "") -> tuple[str, list[dict]]:
    """Analyze a codebase and return both a display string and raw data.

    Args:
        repo_path: Path to the repository root.

    Returns:
        Tuple of (human-readable report, list of per-file analysis dicts).
        The raw data is consumed by the generator and orchestrator agents.
    """
    if not repo_path.strip():
        return "Error: Repository path is required", []

    path_exists, verified_path = verify_path_exists(repo_path)
    if not path_exists:
        return f"Error: {verified_path}", []

    logger.info(f"Analyzing codebase at: {verified_path}")

    analyses = analyze_directory(verified_path)
    report = format_analysis_report(analyses)
    return report, analyses
