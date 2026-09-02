#!/usr/bin/env python3
"""Structural map of a Python module: functions, params, routes, coupling.

Interface surface only -- no implementation bodies. Written for scoping the
LiteLLM fork, where the question is "what is the shape of this file" rather than
"what does it do internally".

Usage:
    python3 scripts/map_module.py litellm/proxy/management_endpoints/ui_sso.py
"""
import ast
import re
import sys


def sig(node):
    """Render a function signature from its AST node."""
    a = node.args
    parts = []
    defaults = [None] * (len(a.args) - len(a.defaults)) + list(a.defaults)
    for arg, dflt in zip(a.args, defaults):
        s = arg.arg
        if arg.annotation:
            s += f": {ast.unparse(arg.annotation)}"
        if dflt is not None:
            s += f" = {ast.unparse(dflt)}"
        parts.append(s)
    if a.vararg:
        parts.append("*" + a.vararg.arg)
    kwdefaults = list(a.kw_defaults)
    for arg, dflt in zip(a.kwonlyargs, kwdefaults):
        s = arg.arg
        if arg.annotation:
            s += f": {ast.unparse(arg.annotation)}"
        if dflt is not None:
            s += f" = {ast.unparse(dflt)}"
        parts.append(s)
    if a.kwarg:
        parts.append("**" + a.kwarg.arg)
    ret = f" -> {ast.unparse(node.returns)}" if node.returns else ""
    return f"({', '.join(parts)}){ret}"


def route_of(node):
    """If this function carries a FastAPI route decorator, return 'METHOD path'."""
    out = []
    for d in node.decorator_list:
        if not isinstance(d, ast.Call):
            continue
        f = d.func
        name = getattr(f, "attr", None)
        if name in {"get", "post", "put", "delete", "patch"} and d.args:
            try:
                out.append(f"{name.upper()} {ast.literal_eval(d.args[0])}")
            except Exception:
                pass
    return out


def first_line_doc(node):
    doc = ast.get_docstring(node)
    return doc.strip().split("\n")[0][:90] if doc else ""


def main(path):
    src = open(path, encoding="utf-8").read()
    lines = src.split("\n")
    tree = ast.parse(src)

    print(f"# {path}\n\n{len(lines)} lines\n")

    # ---- classes ----
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    if classes:
        print("## Classes\n")
        for c in classes:
            bases = ", ".join(ast.unparse(b) for b in c.bases) or "-"
            print(f"- **{c.name}**(_{bases}_) L{c.lineno} — {first_line_doc(c)}")
        print()

    # ---- functions, module level and methods ----
    print("## Functions\n")
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        owner = ""
        for c in classes:
            if any(n is node for n in ast.walk(c)):
                owner = c.name + "."
                break
        kind = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
        routes = route_of(node)
        tag = ("  `[" + "; ".join(routes) + "]`") if routes else ""
        print(f"- L{node.lineno} `{kind} {owner}{node.name}{sig(node)}`{tag}")
        d = first_line_doc(node)
        if d:
            print(f"    - {d}")
    print()

    # ---- coupling ----
    print("## Enterprise coupling\n")
    print("### premium_user gates\n")
    for i, line in enumerate(lines, 1):
        if "premium_user" in line:
            print(f"- L{i}: `{line.strip()[:110]}`")
    print("\n### enterprise imports\n")
    tries = [n for n in ast.walk(tree) if isinstance(n, ast.Try)]
    for node in ast.walk(tree):
        mods = []
        if isinstance(node, ast.ImportFrom) and node.module and "enterprise" in node.module:
            mods = [f"{node.module}.{a.name}" for a in node.names]
        elif isinstance(node, ast.Import):
            mods = [a.name for a in node.names if "enterprise" in a.name]
        if not mods:
            continue
        guarded = any(node in ast.walk(t) for t in tries)
        for m in mods:
            print(f"- L{node.lineno}: `{m}` — {'guarded (try/except)' if guarded else '**UNGUARDED**'}")
    print("\n### EnterpriseCustomSSOHandler usage\n")
    for i, line in enumerate(lines, 1):
        if "EnterpriseCustomSSOHandler" in line:
            print(f"- L{i}: `{line.strip()[:110]}`")

    # ---- providers ----
    print("\n## Identity providers referenced\n")
    providers = ["google", "microsoft", "azure", "okta", "auth0", "generic", "oidc",
                 "saml", "github", "gitlab", "keycloak", "ldap"]
    hits = {}
    low = src.lower()
    for p in providers:
        n = len(re.findall(r"\b" + p + r"\b", low))
        if n:
            hits[p] = n
    for p, n in sorted(hits.items(), key=lambda x: -x[1]):
        print(f"- {p}: {n} references")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: map_module.py <file.py>")
    main(sys.argv[1])
