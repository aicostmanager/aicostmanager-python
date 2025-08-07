import pytest

from aicostmanager.type_validator import TypeValidator


def test_basic_type_validation():
    validator = TypeValidator()
    assert validator.validate_value(1, "int")[0]
    ok, msg = validator.validate_value("1", "int")
    assert not ok
    assert "Expected int" in msg


def test_typed_list_validation():
    validator = TypeValidator()
    assert validator.validate_value([1, 2, 3], "List[int]")[0]
    ok, msg = validator.validate_value([1, "2"], "List[int]")
    assert not ok
    assert "List element at index 1" in msg


def test_typed_dict_validation():
    validator = TypeValidator()
    assert validator.validate_value({"a": 1}, "Dict[str, int]")[0]
    ok, msg = validator.validate_value({1: 1}, "Dict[str, int]")
    assert not ok
    assert "Dict key 1 is int" in msg


def test_optional_and_union_validation():
    validator = TypeValidator()
    assert validator.validate_value(None, "Optional[int]")[0]
    assert validator.validate_value(5, "Optional[int]")[0]
    ok, msg = validator.validate_value("5", "Optional[int]")
    assert not ok
    assert "Expected int" in msg

    assert validator.validate_value("abc", "Union[int, str]")[0]
    ok, msg = validator.validate_value(1.5, "Union[int, str]")
    assert not ok
    assert "Union" in msg


def test_unsupported_type_string():
    validator = TypeValidator()
    ok, msg = validator.validate_value(1, "UnknownType")
    assert not ok
    assert "Unsupported type string" in msg
