import { describe, expect, it } from "vitest";

import { canUserEditGuardrails } from "./canUserEditGuardrails";
import { rolesWithWriteAccess } from "./roles";

describe("canUserEditGuardrails", () => {
  // This fork removed the premiumUser gate (see FORK.md). Upstream computed
  //   premiumUser || (userRole != null && rolesWithWriteAccess.includes(userRole))
  // so with premiumUser unconditionally true the role check never ran and a
  // view-only user could edit guardrails. These tests pin the role check as the
  // sole authority, and exist so that reintroducing an OR'd bypass fails here
  // rather than silently re-opening write access.

  it.each(rolesWithWriteAccess)("allows %s", (role) => {
    expect(canUserEditGuardrails(role)).toBe(true);
  });

  it.each([
    ["Admin Viewer", "Admin Viewer"],
    ["proxy_admin_viewer", "proxy_admin_viewer"],
    ["internal_user_viewer", "internal_user_viewer"],
    ["an unrecognised role", "some_future_role"],
  ])("denies %s", (_label, role) => {
    expect(canUserEditGuardrails(role)).toBe(false);
  });

  it("denies a null role", () => {
    expect(canUserEditGuardrails(null)).toBe(false);
  });

  it("denies an undefined role", () => {
    expect(canUserEditGuardrails(undefined)).toBe(false);
  });

  it("denies an empty string", () => {
    expect(canUserEditGuardrails("")).toBe(false);
  });

  // The regression this whole change exists to prevent: the result must depend
  // only on the role, never on a premium flag. If someone reinstates the OR,
  // a viewer becomes editable and this fails.
  it("is false for a viewer regardless of any premium notion", () => {
    expect(canUserEditGuardrails("proxy_admin_viewer")).toBe(false);
    expect(canUserEditGuardrails("internal_user_viewer")).toBe(false);
  });
});
