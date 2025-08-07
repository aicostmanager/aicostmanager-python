from __future__ import annotations

from typing import Any, Dict, Tuple
import re


class TypeValidator:
    """Validate values against string-specified Python type hints."""

    def __init__(self) -> None:
        self.basic_types = {
            "int": int,
            "float": float,
            "str": str,
            "bool": bool,
            "list": list,
            "dict": dict,
            "tuple": tuple,
            "set": set,
        }
        self.pattern_validators = {
            r"List\[(\w+)\]": self._validate_typed_list,
            r"Dict\[(\w+),\s*(\w+)\]": self._validate_typed_dict,
            r"Optional\[(\w+)\]": self._validate_optional,
            r"Union\[(.+)\]": self._validate_union,
        }

    def validate_value(self, value: Any, type_string: str) -> Tuple[bool, str]:
        """Validate a value against a type string."""
        try:
            if value is None:
                if "Optional" in type_string or "Union" in type_string:
                    return True, ""
                return False, f"Value cannot be None for type {type_string}"

            if type_string in self.basic_types:
                expected = self.basic_types[type_string]
                if isinstance(value, expected):
                    return True, ""
                return False, f"Expected {type_string}, got {type(value).__name__}"

            for pattern, validator in self.pattern_validators.items():
                match = re.match(pattern, type_string)
                if match:
                    return validator(value, match.groups())

            return False, f"Unsupported type string: {type_string}"
        except Exception as exc:
            return False, f"Validation error: {exc}"

    # --- pattern handlers -------------------------------------------------
    def _validate_typed_list(self, value: Any, groups: Tuple[str, ...]) -> Tuple[bool, str]:
        if not isinstance(value, list):
            return False, f"Expected list, got {type(value).__name__}"
        element = groups[0]
        expected = self.basic_types.get(element)
        if expected:
            for idx, item in enumerate(value):
                if not isinstance(item, expected):
                    return False, f"List element at index {idx} is {type(item).__name__}, expected {element}"
        return True, ""

    def _validate_typed_dict(self, value: Any, groups: Tuple[str, ...]) -> Tuple[bool, str]:
        if not isinstance(value, dict):
            return False, f"Expected dict, got {type(value).__name__}"
        key_type, value_type = groups
        key_cls = self.basic_types.get(key_type)
        value_cls = self.basic_types.get(value_type)
        if key_cls and value_cls:
            for k, v in value.items():
                if not isinstance(k, key_cls):
                    return False, f"Dict key {k} is {type(k).__name__}, expected {key_type}"
                if not isinstance(v, value_cls):
                    return False, f"Dict value for key '{k}' is {type(v).__name__}, expected {value_type}"
        return True, ""

    def _validate_optional(self, value: Any, groups: Tuple[str, ...]) -> Tuple[bool, str]:
        inner = groups[0]
        if value is None:
            return True, ""
        return self.validate_value(value, inner)

    def _validate_union(self, value: Any, groups: Tuple[str, ...]) -> Tuple[bool, str]:
        options = [t.strip() for t in groups[0].split(",")]
        for option in options:
            ok, _ = self.validate_value(value, option)
            if ok:
                return True, ""
        return False, f"Value doesn't match any type in Union[{groups[0]}]"
