"""Learning loop: every user confirmation of a parsing rule is persisted;
after AUTO_THRESHOLD consecutive confirmations the rule switches to auto mode
and the agent stops asking. A rejection resets the counter.

Documents live in ctx.store (per-user isolation is the platform's job); the
store assigns its own doc ids, so records are looked up by data["rule_key"].
"""

from __future__ import annotations

RULES_COLLECTION = "rules"
AUTO_THRESHOLD = 3


async def _find_rule_doc(ctx, rule_key: str):
    page = await ctx.store.query(RULES_COLLECTION, limit=100)
    return next((d for d in page.data if d.data.get("rule_key") == rule_key), None)


async def get_rule(ctx, rule_key: str) -> dict | None:
    doc = await _find_rule_doc(ctx, rule_key)
    return doc.data if doc else None


async def is_auto(ctx, rule_key: str) -> bool:
    rule = await get_rule(ctx, rule_key)
    return bool(rule and rule.get("auto"))


async def confirm(ctx, rule_key: str, accepted: bool = True) -> dict:
    """Record one user decision for a rule and return the updated rule state."""
    doc = await _find_rule_doc(ctx, rule_key)
    data = doc.data if doc else {"rule_key": rule_key, "confirmations": 0, "auto": False}
    if accepted:
        data["confirmations"] = int(data.get("confirmations", 0)) + 1
        data["auto"] = data["confirmations"] >= AUTO_THRESHOLD
    else:
        data["confirmations"] = 0
        data["auto"] = False
    data["last_decision"] = accepted
    if doc:
        await ctx.store.update(RULES_COLLECTION, doc.id, data)
    else:
        await ctx.store.create(RULES_COLLECTION, data)
    return data
