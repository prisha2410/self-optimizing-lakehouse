"""
Tests for the decision-validation logic that prevents crashes like the
one we hit in practice: a REPARTITION_BY_COLUMN decision with
target_column: null caused an unhandled ValueError deep in PyIceberg.
"""
import pytest

COLUMN_REQUIRED_ACTIONS = {"REPARTITION_BY_COLUMN", "REMOVE_PARTITION_FIELD", "ADD_SORT_ORDER"}


def is_decision_valid(decision):
    """Mirrors the validation check inside execute_decisions.main().
    Returns (valid: bool, skip_reason: str | None)."""
    action = decision["recommended_action"]

    if action == "NO_ACTION_NEEDED":
        return True, None

    if action in COLUMN_REQUIRED_ACTIONS and not decision.get("target_column"):
        return False, f"action '{action}' requires a target_column but none was given"

    return True, None


def test_repartition_with_null_column_is_rejected():
    """This is the exact bug that crashed the pipeline in practice."""
    decision = {
        "issue": "test",
        "recommended_action": "REPARTITION_BY_COLUMN",
        "target_column": None,
    }
    valid, reason = is_decision_valid(decision)
    assert not valid
    assert "target_column" in reason


def test_repartition_with_valid_column_is_accepted():
    decision = {
        "issue": "test",
        "recommended_action": "REPARTITION_BY_COLUMN",
        "target_column": "customer_id",
    }
    valid, reason = is_decision_valid(decision)
    assert valid
    assert reason is None


def test_compact_files_does_not_require_column():
    decision = {
        "issue": "test",
        "recommended_action": "COMPACT_FILES",
        "target_column": None,
    }
    valid, reason = is_decision_valid(decision)
    assert valid


def test_no_action_needed_is_always_valid():
    decision = {"issue": "test", "recommended_action": "NO_ACTION_NEEDED", "target_column": None}
    valid, reason = is_decision_valid(decision)
    assert valid