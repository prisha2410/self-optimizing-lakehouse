"""
Unit tests for the decision-validation and transform-resolution logic in
agent/execute_decisions.py. These don't require a live Iceberg catalog —
they use lightweight fakes for the table schema/spec.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent"))

import pytest
from pyiceberg.transforms import IdentityTransform, MonthTransform, BucketTransform

from execute_decisions import resolve_transform


class FakeFieldType:
    def __init__(self, type_str):
        self._type_str = type_str

    def __str__(self):
        return self._type_str


class FakeField:
    def __init__(self, name, field_type_str):
        self.name = name
        self.field_type = FakeFieldType(field_type_str)


class FakeSchema:
    def __init__(self, fields):
        self.fields = fields


class FakeTable:
    def __init__(self, fields):
        self._schema = FakeSchema(fields)

    def schema(self):
        return self._schema


# --- resolve_transform tests ---

def test_month_transform_for_order_date():
    table = FakeTable([FakeField("order_date", "timestamp")])
    decision = {"suggested_transform": "month"}
    transform, field_name, reason = resolve_transform(table, "order_date", decision)
    assert isinstance(transform, MonthTransform)
    assert field_name == "order_date_month"
    assert reason is None


def test_bucket_transform_for_high_cardinality_int_column():
    table = FakeTable([FakeField("customer_id", "long")])
    decision = {"suggested_transform": "bucket:16"}
    transform, field_name, reason = resolve_transform(table, "customer_id", decision)
    assert isinstance(transform, BucketTransform)
    assert field_name == "customer_id_bucket_16"
    assert reason is None


def test_bucket_transform_rejected_for_double_column():
    """This is the exact bug we hit in practice: customer_id is a double,
    and Iceberg's bucket transform doesn't support that type."""
    table = FakeTable([FakeField("customer_id", "double")])
    decision = {"suggested_transform": "bucket:16"}
    transform, field_name, reason = resolve_transform(table, "customer_id", decision)
    assert transform is None
    assert field_name is None
    assert "double" in reason
    assert "bucket" in reason.lower()


def test_identity_transform_for_low_cardinality_column():
    table = FakeTable([FakeField("vendor", "string")])
    decision = {"suggested_transform": "identity"}
    transform, field_name, reason = resolve_transform(table, "vendor", decision)
    assert isinstance(transform, IdentityTransform)
    assert field_name == "vendor_partition"
    assert reason is None


def test_missing_suggestion_refuses_to_guess():
    """No suggested_transform at all — must not silently default to identity,
    since that's exactly what caused the over-partitioning incident."""
    table = FakeTable([FakeField("customer_id", "double")])
    decision = {}  # no suggested_transform key
    transform, field_name, reason = resolve_transform(table, "customer_id", decision)
    assert transform is None
    assert field_name is None
    assert reason is not None


def test_malformed_bucket_count_falls_back_to_default():
    table = FakeTable([FakeField("customer_id", "long")])
    decision = {"suggested_transform": "bucket:notanumber"}
    transform, field_name, reason = resolve_transform(table, "customer_id", decision)
    assert isinstance(transform, BucketTransform)
    assert field_name == "customer_id_bucket_16"  # falls back to 16


def test_column_not_in_schema():
    table = FakeTable([FakeField("vendor", "string")])
    decision = {"suggested_transform": "identity"}
    transform, field_name, reason = resolve_transform(table, "nonexistent_column", decision)
    assert transform is None
    assert "not found in schema" in reason