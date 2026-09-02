# About this fork

A fork of [LiteLLM](https://github.com/BerriAI/litellm) containing **only the
MIT-licensed core**.

## What was removed and why

Upstream is dual-licensed. Its root `LICENSE` states:

> Portions of this software are licensed as follows:
> * All content that resides under the "enterprise/" directory of this repository,
>   if that directory exists, is licensed under the license defined in
>   "enterprise/LICENSE".
> * Content outside of the above mentioned directories or restrictions above is
>   available under the MIT license as defined below.

`enterprise/` is under the BerriAI Enterprise License, which we hold no rights to
redistribute. It is **not present in this fork** — 149 files, ~11,500 LOC, removed
in full. The `LICENSE` here is therefore the MIT grant alone, with BerriAI's
copyright notice retained as MIT requires.

Upstream's own CI test
`tests/code_coverage_tests/check_unsafe_enterprise_import.py` fails the build if
any file under `litellm/` imports `enterprise` outside a `try:` block. That test
is kept and passing, which is what makes removal a supported state rather than
surgery: the core is designed to run without that directory.

## What we build instead

Features we want are implemented here, from the interface, as our own work under
MIT. See `FORK-ANALYSIS.md` for the coupling map that scopes it.

Current targets:

| feature | status |
|---|---|
| `allowed_ips` with CIDR support | core has exact-match only; extending |
| OIDC | scoping |
| mTLS | new — not an upstream concept |
| Aider mTLS | new |

## Working agreements

- **Any functional change gets tests.** Ungating alone does not, but changing
  behaviour does — extend the existing parametrised cases rather than bolting on
  new test functions.
- **Keep the enterprise-import invariant passing.** It is a genuinely useful
  guard for a fork that intends to stay decoupled, even with the directory gone.
- **Attribution stays.** The MIT notice and BerriAI copyright are retained
  throughout; that is the condition on which this code is ours to use.

## Upstream

Forked from `BerriAI/litellm` at commit `31ca4dd`, branch
`litellm_internal_staging`, v1.101.0.
