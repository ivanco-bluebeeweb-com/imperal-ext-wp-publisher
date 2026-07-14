import rules


async def test_three_confirmations_switch_to_auto(ctx):
    assert not await rules.is_auto(ctx, "subheading_heuristic")
    for i in range(1, 3):
        state = await rules.confirm(ctx, "subheading_heuristic", True)
        assert state["confirmations"] == i
        assert not state["auto"]
    state = await rules.confirm(ctx, "subheading_heuristic", True)
    assert state["confirmations"] == 3
    assert state["auto"]
    assert await rules.is_auto(ctx, "subheading_heuristic")


async def test_rejection_resets_counter(ctx):
    await rules.confirm(ctx, "r1", True)
    await rules.confirm(ctx, "r1", True)
    state = await rules.confirm(ctx, "r1", False)
    assert state["confirmations"] == 0
    assert not state["auto"]
