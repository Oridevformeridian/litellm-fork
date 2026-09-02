# LiteLLM fork — enterprise coupling analysis

AST/grep scan of `litellm/` at commit `31ca4dd`, 2026-09-02. Regenerate: `python3 scripts/gen_fork_analysis.py`


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

## Scale

- **Mechanism A**: 46 import seams across 17 files (14 hard-fail)
- **Mechanism B**: 60 runtime gates across 26 files
- `enterprise/` itself: 149 files, ~11,500 LOC — all removable


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


---

# Mechanism A — imports from `enterprise/`


## A · auth (3 seams, 2 hard-fail)

| file | line | symbol | fallback when absent |
|---|---|---|---|
| `proxy/auth/route_checks.py` | 77 | `EnterpriseRouteChecks` | **raise**; pass |
| `proxy/auth/user_api_key_auth.py` | 110 | `enterprise_custom_auth` | verbose_proxy_logger.debug('Error in e; `enterprise_custom_auth  |
| `proxy/management_endpoints/ui_sso.py` | 1077 | `EnterpriseCustomSSOHandler` | **raise** |

## A · billing/cost (4 seams, 0 hard-fail)

| file | line | symbol | fallback when absent |
|---|---|---|---|
| `proxy/proxy_server.py` | 566 | `build_billing_metrics_recorder` | `build_billing_metrics_recorder = None`; `shutdown_billing_metri |
| `proxy/proxy_server.py` | 569 | `shutdown_billing_metrics_recorder` | `build_billing_metrics_recorder = None`; `shutdown_billing_metri |
| `proxy/proxy_server.py` | 9550 | `CheckBatchCost` | verbose_proxy_logger.debug('Failed to ; verbose_proxy_logger.deb |
| `proxy/proxy_server.py` | 9581 | `CheckResponsesCost` | verbose_proxy_logger.debug('Failed to ; verbose_proxy_logger.deb |

## A · email (16 seams, 0 hard-fail)

| file | line | symbol | fallback when absent |
|---|---|---|---|
| `litellm_core_utils/custom_logger_registry.py` | 117 | `ResendEmailLogger` | pass |
| `litellm_core_utils/custom_logger_registry.py` | 120 | `SendGridEmailLogger` | pass |
| `litellm_core_utils/custom_logger_registry.py` | 123 | `SMTPEmailLogger` | pass |
| `litellm_core_utils/litellm_logging.py` | 208 | `ResendEmailLogger` | verbose_logger.debug('[Non-Blocking] U; `GenericAPILogger = Cust |
| `litellm_core_utils/litellm_logging.py` | 211 | `SendGridEmailLogger` | verbose_logger.debug('[Non-Blocking] U; `GenericAPILogger = Cust |
| `litellm_core_utils/litellm_logging.py` | 214 | `SMTPEmailLogger` | verbose_logger.debug('[Non-Blocking] U; `GenericAPILogger = Cust |
| `proxy/hooks/key_management_event_hooks.py` | 419 | `BaseEmailLogger` | pass |
| `proxy/hooks/key_management_event_hooks.py` | 458 | `BaseEmailLogger` | pass |
| `proxy/hooks/key_management_event_hooks.py` | 461 | `SendKeyCreatedEmailEvent` | pass |
| `proxy/hooks/key_management_event_hooks.py` | 528 | `BaseEmailLogger` | verbose_proxy_logger.debug('Enterprise; Return |
| `proxy/hooks/key_management_event_hooks.py` | 537 | `SendKeyRotatedEmailEvent` | verbose_proxy_logger.debug('Enterprise; Return |
| `proxy/hooks/user_management_event_hooks.py` | 130 | `BaseEmailLogger` | verbose_proxy_logger.warning('Defaulti; Return |
| `proxy/utils.py` | 46 | `BaseEmailLogger` | `BaseEmailLogger = None`; `SendGridEmailLogger = None`; `SMTPEma |
| `proxy/utils.py` | 49 | `ResendEmailLogger` | `BaseEmailLogger = None`; `SendGridEmailLogger = None`; `SMTPEma |
| `proxy/utils.py` | 52 | `SendGridEmailLogger` | `BaseEmailLogger = None`; `SendGridEmailLogger = None`; `SMTPEma |
| `proxy/utils.py` | 55 | `SMTPEmailLogger` | `BaseEmailLogger = None`; `SendGridEmailLogger = None`; `SMTPEma |

## A · guardrails (11 seams, 11 hard-fail)

| file | line | symbol | fallback when absent |
|---|---|---|---|
| `integrations/custom_guardrail.py` | 907 | `EnterpriseCustomGuardrailHelper` | **raise** |
| `integrations/custom_guardrail.py` | 934 | `EnterpriseCustomGuardrailHelper` | **raise** |
| `proxy/common_utils/callback_utils.py` | 187 | `_ENTERPRISE_LlamaGuard` | **raise** |
| `proxy/common_utils/callback_utils.py` | 202 | `_ENTERPRISE_SecretDetection` | **raise** |
| `proxy/common_utils/callback_utils.py` | 217 | `_ENTERPRISE_OpenAI_Moderation` | **raise** |
| `proxy/common_utils/callback_utils.py` | 252 | `_ENTERPRISE_GoogleTextModeration` | **raise** |
| `proxy/common_utils/callback_utils.py` | 268 | `_ENTERPRISE_LLMGuard` | **raise** |
| `proxy/common_utils/callback_utils.py` | 281 | `_ENTERPRISE_BlockedUserList` | **raise** |
| `proxy/common_utils/callback_utils.py` | 296 | `_ENTERPRISE_BannedKeywords` | **raise** |
| `proxy/guardrails/guardrail_initializers.py` | 148 | `_ENTERPRISE_SecretDetection` | **raise** |
| `proxy/management_endpoints/customer_endpoints.py` | 217 | `_ENTERPRISE_BlockedUserList` | **raise** |

## A · hooks (2 seams, 1 hard-fail)

| file | line | symbol | fallback when absent |
|---|---|---|---|
| `proxy/hooks/__init__.py` | 49 | `ENTERPRISE_PROXY_HOOKS` | `ENTERPRISE_PROXY_HOOKS = {}` |
| `proxy/response_api_endpoints/endpoints.py` | 371 | `_PROXY_LiteLLMManagedFiles` | AnnAssign; await proxy_logging_obj.post_call_fail; AnnAssign; An |

## A · key/team mgmt (1 seams, 0 hard-fail)

| file | line | symbol | fallback when absent |
|---|---|---|---|
| `proxy/management_endpoints/key_management_endpoints.py` | 1093 | `apply_enterprise_key_management_params` | verbose_proxy_logger.debug('litellm.pr |

## A · logging (4 seams, 0 hard-fail)

| file | line | symbol | fallback when absent |
|---|---|---|---|
| `litellm_core_utils/custom_logger_registry.py` | 114 | `PagerDutyAlerting` | pass |
| `litellm_core_utils/litellm_logging.py` | 202 | `EnterpriseCallbackControls` | verbose_logger.debug('[Non-Blocking] U; `GenericAPILogger = Cust |
| `litellm_core_utils/litellm_logging.py` | 205 | `PagerDutyAlerting` | verbose_logger.debug('[Non-Blocking] U; `GenericAPILogger = Cust |
| `litellm_core_utils/litellm_logging.py` | 217 | `StandardLoggingPayloadSetup` | verbose_logger.debug('[Non-Blocking] U; `GenericAPILogger = Cust |

## A · other (3 seams, 0 hard-fail)

| file | line | symbol | fallback when absent |
|---|---|---|---|
| `proxy/proxy_server.py` | 769 | `enterprise` | Try |
| `proxy/proxy_server.py` | 769 | `enterprise` | pass |
| `proxy/proxy_server.py` | 776 | `router` | `enterprise_proxy_config = None` |

## A · proxy config (2 seams, 0 hard-fail)

| file | line | symbol | fallback when absent |
|---|---|---|---|
| `proxy/proxy_server.py` | 777 | `EnterpriseProxyConfig` | `enterprise_proxy_config = None` |
| `proxy/public_endpoints/public_endpoints.py` | 352 | `EnterpriseProxyConfig` | `custom_docs_description = None` |

---

# Mechanism B — `premium_user` runtime gates

_Implementations already present in the MIT core; gated by a flag._


## B · auth (10 gates)

| file | line | condition | feature |
|---|---|---|---|
| `proxy/auth/auth_utils.py` | 598 | `if premium_user is not True:` | Trying to set allowed_routes. This is an Enterprise feature. %s |
| `proxy/auth/auth_utils.py` | 636 | `if premium_user is not True:` |  |
| `proxy/auth/auth_utils.py` | 851 | `if premium_user is not True:` | using max_request_size_mb - not checking -  this is an enterprise only fea |
| `proxy/auth/auth_utils.py` | 912 | `if premium_user is not True:` | using max_response_size_mb - not checking -  this is an enterprise only fe |
| `proxy/auth/route_checks.py` | 346 | `if premium_user is not True:` |  this is an Enterprise only feature. %s |
| `proxy/auth/user_api_key_auth.py` | 1350 | `if premium_user is not True:` | Oauth2 token validation is only available for premium users.  |
| `proxy/auth/user_api_key_auth.py` | 1370 | `if premium_user is not True:` | JWT Auth is an enterprise only feature. {CommonProxyErrors.not_premium_use |
| `proxy/management_endpoints/ui_sso.py` | 991 | `if premium_user is True:` |  |
| `proxy/management_endpoints/ui_sso.py` | 4590 | `if premium_user is not True:` | You must be a LiteLLM Enterprise user to use SSO. If you have a license pl |
| `proxy/proxy_server.py` | 5566 | `if allowed_ips is not None and premium_user is False:` | allowed_ips is an Enterprise Feature. Please add a valid LITELLM_LICENSE t |

## B · billing/cost (5 gates)

| file | line | condition | feature |
|---|---|---|---|
| `proxy/management_endpoints/key_management_endpoints.py` | 4154 | `if "get_spend_routes" in saved_token["permissions"] and ` | get_spend_routes permission is only available for LiteLLM Enterprise users |
| `proxy/management_endpoints/key_management_endpoints.py` | 7046 | `if premium_user is not True:` | You must have an enterprise license to set model_max_budget. {CommonProxyE |
| `proxy/spend_tracking/spend_management_endpoints.py` | 1268 | `if premium_user is not True:` | accessing /spend/report but not a premium user |
| `proxy/spend_tracking/spend_management_endpoints.py` | 1583 | `if premium_user is not True:` |  |
| `router_strategy/budget_limiter.py` | 829 | `if premium_user is not True:` | Tag budgets are an Enterprise only feature, {CommonProxyErrors.not_premium |

## B · guardrails (3 gates)

| file | line | condition | feature |
|---|---|---|---|
| `integrations/custom_guardrail.py` | 999 | `if self._validate_premium_user() is not True:` | Guardrail %s: ignoring dynamic extra_body keys %s because premium_user is  |
| `integrations/custom_guardrail.py` | 1002 | `"Guardrail %s: ignoring dynamic extra_body keys %s becau` | Guardrail %s: ignoring dynamic extra_body keys %s because premium_user is  |
| `integrations/custom_guardrail.py` | 1019 | `if premium_user is not True:` | Trying to use premium guardrail without premium user %s |

## B · key/team mgmt (6 gates)

| file | line | condition | feature |
|---|---|---|---|
| `proxy/management_endpoints/key_management_endpoints.py` | 1178 | `if premium_user is not True and data_json["tags"] is not` | Only premium users can add tags to keys. {CommonProxyErrors.not_premium_us |
| `proxy/management_endpoints/key_management_endpoints.py` | 3922 | `if not premium_user:` | Setting a model access group on a wildcard model is only available for Lit |
| `proxy/management_endpoints/key_management_endpoints.py` | 5140 | `premium_user is not True and not is_master_key_regenerat` | Regenerating Virtual Keys is an Enterprise feature, {CommonProxyErrors.not |
| `proxy/management_endpoints/team_endpoints.py` | 2433 | `if premium_user is not True:` | Assigning team admins is a premium feature. {CommonProxyErrors.not_premium |
| `proxy/management_endpoints/team_endpoints.py` | 2438 | `if premium_user is not True:` | Assigning team admins is a premium feature. Got={m}. {CommonProxyErrors.no |
| `proxy/management_endpoints/team_endpoints.py` | 3425 | `if data.role == "admin" and not premium_user:` | Assigning team admins is a premium feature. You must be a LiteLLM Enterpri |

## B · logging (1 gates)

| file | line | condition | feature |
|---|---|---|---|
| `integrations/SlackAlerting/slack_alerting.py` | 1216 | `if premium_user is not True:` | Trying to Customize Email Alerting\n {CommonProxyErrors.not_premium_user.v |

## B · model mgmt (6 gates)

| file | line | condition | feature |
|---|---|---|---|
| `proxy/fine_tuning_endpoints/endpoints.py` | 111 | `if premium_user is not True:` | Only premium users can use this endpoint + {CommonProxyErrors.not_premium_ |
| `proxy/fine_tuning_endpoints/endpoints.py` | 260 | `if premium_user is not True:` | Only premium users can use this endpoint + {CommonProxyErrors.not_premium_ |
| `proxy/fine_tuning_endpoints/endpoints.py` | 412 | `if premium_user is not True:` | Only premium users can use this endpoint + {CommonProxyErrors.not_premium_ |
| `proxy/fine_tuning_endpoints/endpoints.py` | 533 | `if premium_user is not True:` | Only premium users can use this endpoint + {CommonProxyErrors.not_premium_ |
| `proxy/management_endpoints/model_management_endpoints.py` | 1460 | `if premium_user is False:` |  |
| `proxy/management_endpoints/model_management_endpoints.py` | 1511 | `if model_params.model_info.team_id is not None and premi` |  |

## B · other (26 gates)

| file | line | condition | feature |
|---|---|---|---|
| `integrations/azure_storage/azure_storage.py` | 300 | `if premium_user is not True:` | AzureBlobStorageLogger is only available for premium users. {CommonProxyEr |
| `integrations/gcs_bucket/gcs_bucket.py` | 49 | `if premium_user is not True:` | GCS Bucket logging is a premium feature. Please upgrade to use it. {Common |
| `integrations/gcs_bucket/gcs_bucket.py` | 58 | `if premium_user is not True:` | GCS Bucket logging is a premium feature. Please upgrade to use it. {Common |
| `proxy/auth/oauth2_check.py` | 131 | `if premium_user is not True:` | Oauth2 token validation is only available for premium users |
| `proxy/common_utils/callback_utils.py` | 195 | `if premium_user is not True:` |  |
| `proxy/common_utils/callback_utils.py` | 210 | `if premium_user is not True:` |  |
| `proxy/common_utils/callback_utils.py` | 226 | `if premium_user is not True:` |  |
| `proxy/common_utils/callback_utils.py` | 261 | `if premium_user is not True:` |  |
| `proxy/common_utils/callback_utils.py` | 274 | `if premium_user is not True:` |  |
| `proxy/common_utils/callback_utils.py` | 289 | `if premium_user is not True:` | Trying to use ENTERPRISE BlockedUser |
| `proxy/common_utils/callback_utils.py` | 304 | `if premium_user is not True:` | Trying to use ENTERPRISE BannedKeyword |
| `proxy/common_utils/http_parsing_utils.py` | 252 | `if not premium_user:` | Tried setting max_file_size_mb for /audio/transcriptions. {CommonProxyErro |
| `proxy/health_endpoints/_health_endpoints.py` | 1338 | `license_type: Final = "enterprise" if premium_user else ` |  |
| `proxy/litellm_pre_call_utils.py` | 2624 | `if enforced_params and premium_user is not True:` | Enforced Params is an Enterprise feature. Enforced Params: {enforced_param |
| `proxy/management_helpers/audit_logs.py` | 40 | `return premium_user is True` |  |
| `proxy/management_helpers/audit_logs.py` | 216 | `if premium_user is not True:` |  |
| `proxy/management_helpers/team_metadata_validation.py` | 111 | `if premium_user is not True:` | custom_team_metadata_validate is an Enterprise feature. {CommonProxyErrors |
| `proxy/proxy_server.py` | 855 | `_title: Final = os.getenv("DOCS_TITLE", "LiteLLM API") i` | ) if premium_user else  |
| `proxy/proxy_server.py` | 861 | `if premium_user` |  |
| `proxy/proxy_server.py` | 1061 | `if premium_user is False:` |  |
| `proxy/proxy_server.py` | 1575 | `if os.getenv("DOCS_FILTERED", "False") == "True" and pre` |  |
| `proxy/proxy_server.py` | 5630 | `if general_settings.get("enforced_params") is not None a` |  |
| `proxy/proxy_server.py` | 5837 | `if premium_user is not True:` |  |
| `proxy/proxy_server.py` | 5993 | `if premium_user is True:` |  |
| `proxy/proxy_server.py` | 18046 | `is_request_size_limit_enabled=lambda: premium_user is Tr` |  |
| `proxy/utils.py` | 7127 | `if not premium_user:` |  |

## B · secrets/KMS (3 gates)

| file | line | condition | feature |
|---|---|---|---|
| `secret_managers/cyberark_secret_manager.py` | 55 | `if premium_user is not True:` | CyberArk secret manager is only available for premium users. {CommonProxyE |
| `secret_managers/google_secret_manager.py` | 27 | `if premium_user is not True:` | Google Secret Manager requires an Enterprise License {CommonProxyErrors.no |
| `secret_managers/hashicorp_secret_manager.py` | 115 | `if premium_user is not True:` | Hashicorp secret manager is only available for premium users. {CommonProxy |


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


---

# AUTH cluster — implementation survey

Read statically from the MIT core. For each gated feature: is the implementation
actually present, is it complete, and does ungating alone give us what we want?

## Classification

| feature | mechanism | implementation | verdict |
|---|---|---|---|
| `allowed_ips` | B | `auth_utils.py:87-105` `_check_valid_ip` | present but **exact-match only** — needs extending |
| `allowed_routes` | B | `auth_utils.py:598` | present |
| `admin_only_routes` | B | `route_checks.py:346` | present |
| `max_request_size_mb` | B | `auth_utils.py:851` | present |
| `max_response_size_mb` | B | `auth_utils.py:912` | present |
| OAuth2 token validation | B | `user_api_key_auth.py:1350` | present |
| JWT auth | B | `user_api_key_auth.py:1370` | present |
| SSO | **A + B** | flag gates in `ui_sso.py`, **plus** `EnterpriseCustomSSOHandler` import at :1077 | split — partly absent |
| custom auth hook | A | `user_api_key_auth.py:110`, fallback is non-fatal | soft plug-in point |
| mTLS | neither | absent upstream | new work |

The headline: **OAuth2 and JWT auth are both mechanism B**, implementations
present. For the OIDC target that likely means decoupling rather than building.

## `allowed_ips` needs more than ungating

    # auth_utils.py:102
    if client_ip not in allowed_ips:

Exact string membership against a list. No CIDR. For the fleet we want
`10.8.0.0/24` (the wg mesh), not eight literal addresses — so this is a
FUNCTIONAL change, not just an ungate, and it needs tests.

### Existing coverage

`tests/proxy_unit_tests/test_user_api_key_auth.py` has two parametrised tests:

- `test_check_valid_ip` — 6 cases
- `test_check_valid_ip_sent_with_x_forwarded_for` — 6 cases

Both cover exact-match and the no-client-IP case. **Zero CIDR cases** (verified:
no `/24`, `/16`, `/8`, `cidr` or `subnet` anywhere near them).

### Cases to add when CIDR lands

Extend both parametrised lists rather than writing new test functions — the
existing shape already takes `(allowed_ips, client_ip, expected)`:

- `(["10.8.0.0/24"], "10.8.0.9", True)` — in range (bazzite)
- `(["10.8.0.0/24"], "10.8.1.9", False)` — outside range
- `(["10.8.0.0/24"], "10.8.0.0", True)` — network address
- `(["10.8.0.0/24"], "10.8.0.255", True)` — broadcast address
- `(["10.8.0.5"], "10.8.0.5", True)` — bare IP still works (no regression)
- `(["10.8.0.0/24", "192.168.20.17"], "192.168.20.17", True)` — mixed list
- `(["10.8.0.0/24"], "not-an-ip", False)` — malformed client IP does not throw
- `(["garbage/24"], "10.8.0.9", False)` — malformed rule does not throw
- `(["::1/128"], "::1", True)` — IPv6, since `ip_address` handles both
- `([], "10.8.0.9", False)` — empty list still denies (no regression)

The last two matter most: a malformed entry must not raise inside an auth path,
because an exception there is a failure mode with security consequences rather
than a bug. `ipaddress.ip_network(..., strict=False)` plus a guarded parse is
the shape.

## mTLS — design question before code

Not a LiteLLM concept at all. Decide where TLS terminates:

- **Reverse proxy terminates** (Caddy/nginx in front) — it validates the client
  cert and passes a verified identity header. LiteLLM only reads that header,
  so the work lands in the custom-auth hook at `user_api_key_auth.py:110`, whose
  fallback is already non-fatal. Smallest change, and it composes with the
  existing `trusted proxy CIDR` settings in `_types.py:2676` which exist
  precisely so forwarded headers are only trusted from known proxies.
- **LiteLLM terminates** — needs uvicorn SSL context with `ssl_cert_reqs`, and
  the cert never reaches application code cleanly. More invasive.

The first is almost certainly right, and notably reuses machinery that is
already MIT and already present.
