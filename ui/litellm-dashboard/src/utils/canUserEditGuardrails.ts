import { rolesWithWriteAccess } from "./roles";

/**
 * Whether a user may edit guardrail settings on a key.
 *
 * Upstream computed this inline in three components as:
 *
 *     premiumUser || (userRole != null && rolesWithWriteAccess.includes(userRole))
 *
 * That OR'd a paywall onto a real authorisation check. This fork does not meter
 * features, so `premiumUser` is always true, which made the whole expression
 * constant and silently bypassed the role restriction -- a view-only user could
 * edit guardrails. The premium bypass is dropped and the role check kept, since
 * the role check is the part that was ever actually authorisation.
 *
 * Extracted to one place because the same expression appeared in
 * create_key_button.tsx, key_edit_view.tsx and key_info_view.tsx. Three copies
 * of a security predicate is three chances to fix two of them.
 */
export function canUserEditGuardrails(userRole: string | null | undefined): boolean {
  return userRole != null && rolesWithWriteAccess.includes(userRole);
}
