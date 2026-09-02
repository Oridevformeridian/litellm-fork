"""Generate FORK-ANALYSIS.md — both gating mechanisms, from a live AST/grep scan."""
import ast, os, re, subprocess, datetime, collections

ROOT = "litellm"

CLUSTERS = [
    ("auth", ("user_api_key_auth", "route_checks", "ui_sso", "SSO", "auth_utils",
              "allowed_ips", "allowed_routes", "admin_only", "enforced_params", "jwt")),
    ("guardrails", ("_ENTERPRISE_", "custom_guardrail", "guardrail")),
    ("email", ("EmailLogger", "SendKey", "send_emails", "Resend", "SendGrid", "SMTP", "email")),
    ("billing/cost", ("billing_metrics", "CheckBatchCost", "CheckResponsesCost", "spend", "budget")),
    ("key/team mgmt", ("key_management", "team_endpoints", "regenerat", "customer_endpoints")),
    ("model mgmt", ("model_management", "fine_tuning", "pass_through")),
    ("proxy config", ("EnterpriseProxyConfig", "custom_docs", "public_endpoints")),
    ("hooks", ("ENTERPRISE_PROXY_HOOKS", "ManagedFiles", "hooks")),
    ("logging", ("custom_logger_registry", "litellm_logging", "PagerDuty", "prometheus", "alerting")),
    ("secrets/KMS", ("KeyManagementService", "AWSKey", "secret_manager")),
]


def cluster_of(*hay):
    h = " ".join(hay)
    for label, keys in CLUSTERS:
        if any(k in h for k in keys):
            return label
    return "other"


# ---------- mechanism A: imports from enterprise/ ----------
def describe(node):
    bits = []
    for n in node.body:
        if isinstance(n, ast.Pass):
            bits.append("pass")
        elif isinstance(n, ast.Assign):
            tgt = ", ".join(t.id for t in n.targets if isinstance(t, ast.Name)) or "attr"
            bits.append(f"`{tgt} = {ast.unparse(n.value)[:24]}`")
        elif isinstance(n, ast.Raise):
            bits.append("**raise**")
        elif isinstance(n, ast.Expr):
            bits.append(ast.unparse(n)[:38])
        else:
            bits.append(type(n).__name__)
    return "; ".join(bits) or "(empty)"


mech_a = []
for dirpath, _, files in os.walk(ROOT):
    for fn in files:
        if not fn.endswith(".py"):
            continue
        path = os.path.join(dirpath, fn)
        try:
            tree = ast.parse(open(path, encoding="utf-8").read())
        except Exception:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Try):
                continue
            found = []
            for sub in ast.walk(node):
                if isinstance(sub, ast.ImportFrom) and sub.module and "enterprise" in sub.module:
                    found += [(a.name, sub.lineno) for a in sub.names]
                elif isinstance(sub, ast.Import):
                    found += [(a.name, sub.lineno) for a in sub.names if "enterprise" in a.name]
            if not found:
                continue
            fb = "; ".join(describe(h) for h in node.handlers)
            for name, line in found:
                mech_a.append({
                    "file": path.replace("litellm/", ""), "line": line, "symbol": name,
                    "fallback": fb[:64], "cluster": cluster_of(path, name), "hard": "raise" in fb,
                })

# ---------- mechanism B: premium_user runtime gates ----------
mech_b = []
msg_re = re.compile(r"""["']([^"']*(?:Enterprise|premium)[^"']*)["']""", re.I)
for dirpath, _, files in os.walk(ROOT):
    for fn in files:
        if not fn.endswith(".py"):
            continue
        path = os.path.join(dirpath, fn)
        if "test" in path:
            continue
        try:
            lines = open(path, encoding="utf-8").read().split("\n")
        except Exception:
            continue
        for i, line in enumerate(lines):
            if "premium_user" not in line:
                continue
            if not re.search(r"\bif\b.*premium_user|premium_user\s*(is|==)", line):
                continue
            # look ahead a few lines for the message that names the feature
            msg = ""
            for j in range(i, min(i + 6, len(lines))):
                m = msg_re.search(lines[j])
                if m and len(m.group(1)) > 12:
                    msg = m.group(1)[:74]
                    break
            mech_b.append({
                "file": path.replace("litellm/", ""), "line": i + 1,
                "cond": line.strip()[:56], "feature": msg,
                "cluster": cluster_of(path, msg),
            })

commit = subprocess.run(["git", "log", "-1", "--format=%h"], capture_output=True, text=True).stdout.strip()
a_by = collections.defaultdict(list)
for r in mech_a:
    a_by[r["cluster"]].append(r)
b_by = collections.defaultdict(list)
for r in mech_b:
    b_by[r["cluster"]].append(r)

o = []
o.append("# LiteLLM fork — enterprise coupling analysis\n")
o.append(f"AST/grep scan of `{ROOT}/` at commit `{commit}`, {datetime.date.today().isoformat()}. "
         f"Regenerate: `python3 scripts/gen_fork_analysis.py`\n")
o.append("""
## Goal

Fork the MIT core, remove what we do not own, and build our own implementations
of the features we want. This maps where the upstream gates live, read from the
core side only.

## There are TWO gating mechanisms, not one

| | mechanism | code location | licence | removal |
|---|---|---|---|---|
| **A** | import from `enterprise/` | outside MIT | BerriAI Enterprise | delete the directory |
| **B** | `premium_user` runtime flag | **inside `litellm/`** | **MIT** | edit the flag or the call sites |

**A** is proprietary code we do not have rights to redistribute — it gets deleted
and, where we want the feature, reimplemented from the interface.

**B** is a different thing entirely: the implementations are already in the MIT
core, complete and working, behind a boolean. `allowed_ips` is the clearest
example — the whole check is `proxy/auth/auth_utils.py:88-102`, MIT-licensed,
and the only obstacle is a flag test in `proxy_server.py`. MIT grants
modification without restriction.

## The choke point

`litellm/proxy/auth/litellm_license.py` → `LicenseCheck.is_premium() -> bool`

    proxy_server.py:787   premium_user: bool = _license_check.is_premium()

`is_premium()` reads `LITELLM_LICENSE`, then validates either by RSA signature
against a bundled public key, or by **calling out to `https://license.litellm.ai`**.
That phone-home is worth removing on its own merits for an air-gapped or
self-hosted fleet, independent of any licensing question.

Every one of the mechanism-B gates below branches on that single bool.
""")

o.append("## Scale\n")
o.append(f"- **Mechanism A**: {len(mech_a)} import seams across {len({r['file'] for r in mech_a})} files "
         f"({sum(1 for r in mech_a if r['hard'])} hard-fail)")
o.append(f"- **Mechanism B**: {len(mech_b)} runtime gates across {len({r['file'] for r in mech_b})} files")
o.append(f"- `enterprise/` itself: 149 files, ~11,500 LOC — all removable\n")

o.append("""
## Two strategies

### 1. Spike — find out what actually matters

Before reimplementing anything, learn which gated features are worth having.
One boolean governs all of mechanism B, so a throwaway local build answers it:
flip `is_premium()` to return `True`, start the proxy, exercise the features,
and note which ones you would actually use. Mechanism A features stay dark
regardless (the code is genuinely absent), which is itself a useful signal —
anything still broken with the flag flipped needs real reimplementation.

**This is a throwaway diagnostic, not the fork.** Its output is a shortlist, not
a build. Do not ship it.

### 2. Rip out — the actual fork

- Delete `enterprise/` (mechanism A gone; the CI invariant already guarantees the
  core tolerates its absence).
- Delete `litellm/proxy/auth/litellm_license.py` and the `LicenseCheck` import,
  which also removes the `license.litellm.ai` phone-home.
- Remove the `premium_user` branches, keeping the implementation side of each.
- Reimplement, from the interface, only what the spike showed was worth having.
- Keep `tests/code_coverage_tests/check_unsafe_enterprise_import.py` running: it
  is a genuinely useful invariant for a fork that intends to stay decoupled.
""")

o.append("\n---\n\n# Mechanism A — imports from `enterprise/`\n")
for c in sorted(a_by):
    rs = a_by[c]
    o.append(f"\n## A · {c} ({len(rs)} seams, {sum(1 for r in rs if r['hard'])} hard-fail)\n")
    o.append("| file | line | symbol | fallback when absent |")
    o.append("|---|---|---|---|")
    for r in sorted(rs, key=lambda x: (x["file"], x["line"])):
        o.append(f"| `{r['file']}` | {r['line']} | `{r['symbol']}` | {r['fallback']} |")

o.append("\n---\n\n# Mechanism B — `premium_user` runtime gates\n")
o.append("_Implementations already present in the MIT core; gated by a flag._\n")
for c in sorted(b_by):
    rs = b_by[c]
    o.append(f"\n## B · {c} ({len(rs)} gates)\n")
    o.append("| file | line | condition | feature |")
    o.append("|---|---|---|---|")
    for r in sorted(rs, key=lambda x: (x["file"], x["line"])):
        o.append(f"| `{r['file']}` | {r['line']} | `{r['cond']}` | {r['feature']} |")

o.append("""

---

# Target features

| feature | mechanism | status |
|---|---|---|
| `allowed_ips` | **B** | implementation complete in MIT core (`proxy/auth/auth_utils.py:88-102`) |
| SSO / OIDC | **A + B** | `ui_sso.py` has both an `EnterpriseCustomSSOHandler` import and multiple flag gates |
| mTLS | neither | absent upstream — new work |
| Aider mTLS | neither | new work |

mTLS is not a LiteLLM concept at all. Decide early whether TLS terminates at the
proxy or in front of it: if a reverse proxy terminates, LiteLLM only reads a
verified-client header, and the work is mostly in the auth hook rather than in
LiteLLM itself.
""")

open("FORK-ANALYSIS.md", "w").write("\n".join(o) + "\n")
print("  mechanism A: %d seams / %d files" % (len(mech_a), len({r["file"] for r in mech_a})))
print("  mechanism B: %d gates / %d files" % (len(mech_b), len({r["file"] for r in mech_b})))
print("  clusters: A=%d B=%d" % (len(a_by), len(b_by)))
