from __future__ import annotations

import pytest
from pydantic import ValidationError

from aicostmanager.models import (
    Condition,
    CostUnitSwitch,
    CustomCostUnitIn,
    CustomCostUnitOut,
    CustomServiceConfiguration,
    CustomServiceFilter,
    CustomServiceIn,
    CustomServiceOut,
    CustomServiceSummaryOut,
    Mapping,
    MappingGroup,
    RoundingConfig,
)


class TestCustomCostUnitModels:
    """Test custom cost unit models."""

    def test_custom_cost_unit_in_valid(self):
        """Test valid CustomCostUnitIn creation."""
        unit = CustomCostUnitIn(
            name="api-calls",
            cost="0.05",
            unit="request",
            per_quantity=1,
            min_units=0,
            max_units=10000,
            currency="USD",
            is_active=True,
        )
        assert unit.name == "api-calls"
        assert unit.cost == "0.05"
        assert unit.unit == "request"
        assert unit.currency == "USD"
        assert unit.is_active is True

    def test_custom_cost_unit_in_defaults(self):
        """Test CustomCostUnitIn with default values."""
        unit = CustomCostUnitIn(
            name="tokens",
            cost=0.001,
            unit="token",
        )
        assert unit.per_quantity == 1
        assert unit.min_units == 0
        assert unit.max_units == 10000000
        assert unit.currency == "USD"
        assert unit.is_active is True

    def test_custom_cost_unit_out_valid(self):
        """Test valid CustomCostUnitOut creation."""
        unit = CustomCostUnitOut(
            name="api-calls",
            cost="0.05",
            unit="request",
            per_quantity=1,
            min_units=0,
            max_units=10000,
            currency="USD",
            is_active=True,
        )
        assert unit.name == "api-calls"
        assert unit.cost == "0.05"


class TestMappingModels:
    """Test mapping-related models."""

    def test_rounding_config_valid(self):
        """Test valid RoundingConfig creation."""
        config = RoundingConfig(
            mode="ceil",
            increment=1000,
        )
        assert config.mode == "ceil"
        assert config.increment == 1000

    def test_rounding_config_minimal(self):
        """Test RoundingConfig with minimal fields."""
        config = RoundingConfig(mode="round")
        assert config.mode == "round"
        assert config.increment is None

    def test_condition_equals(self):
        """Test Condition with equals."""
        condition = Condition(
            equals={"path": "tier", "value": "premium"}
        )
        assert condition.equals == {"path": "tier", "value": "premium"}
        assert condition.regex is None

    def test_condition_regex(self):
        """Test Condition with regex."""
        condition = Condition(
            regex={"path": "user_id", "pattern": "^bot_"}
        )
        assert condition.regex == {"path": "user_id", "pattern": "^bot_"}
        assert condition.equals is None

    def test_cost_unit_switch_valid(self):
        """Test valid CostUnitSwitch creation."""
        switch = CostUnitSwitch(
            field="plan",
            cases={"premium": "premium-tier", "enterprise": "enterprise-tier"},
            default="basic-tier",
        )
        assert switch.field == "plan"
        assert switch.cases["premium"] == "premium-tier"
        assert switch.default == "basic-tier"

    def test_mapping_basic(self):
        """Test basic Mapping creation."""
        mapping = Mapping(
            cost_unit="api-calls",
            field="request_count",
        )
        assert mapping.cost_unit == "api-calls"
        assert mapping.field == "request_count"
        assert mapping.divide_by is None
        assert mapping.multiply_by is None

    def test_mapping_advanced(self):
        """Test advanced Mapping with all options."""
        rounding = RoundingConfig(mode="ceil", increment=1000)
        condition = Condition(equals={"path": "model", "value": "gpt-4"})

        mapping = Mapping(
            cost_unit="tokens",
            field="usage.input_tokens",
            divide_by=1000,
            multiply_by=1.1,
            min_value=1,
            max_value=100000,
            rounding=rounding,
            only_if=condition,
        )
        assert mapping.cost_unit == "tokens"
        assert mapping.divide_by == 1000
        assert mapping.multiply_by == 1.1
        assert mapping.min_value == 1
        assert mapping.max_value == 100000
        assert mapping.rounding.mode == "ceil"
        assert mapping.only_if.equals["value"] == "gpt-4"

    def test_mapping_with_cost_unit_switch(self):
        """Test Mapping with cost unit switch."""
        switch = CostUnitSwitch(
            field="tier",
            cases={"premium": "premium-tokens"},
            default="basic-tokens",
        )

        mapping = Mapping(
            cost_unit_switch=switch,
            field="usage.tokens",
            divide_by=1000,
        )
        assert mapping.cost_unit is None
        assert mapping.cost_unit_switch.field == "tier"
        assert mapping.divide_by == 1000

    def test_mapping_group_valid(self):
        """Test valid MappingGroup creation."""
        condition = Condition(equals={"path": "tier", "value": "premium"})
        mapping = Mapping(cost_unit="premium-tokens", field="usage.tokens")

        group = MappingGroup(
            when=condition,
            mappings=[mapping],
        )
        assert group.when.equals["value"] == "premium"
        assert len(group.mappings) == 1
        assert group.mappings[0].cost_unit == "premium-tokens"


class TestCustomServiceConfiguration:
    """Test custom service configuration models."""

    def test_configuration_basic(self):
        """Test basic CustomServiceConfiguration."""
        cost_unit = CustomCostUnitIn(
            name="requests",
            cost="0.01",
            unit="request",
        )
        mapping = Mapping(
            cost_unit="requests",
            field="request_count",
        )

        config = CustomServiceConfiguration(
            cost_units=[cost_unit],
            mappings=[mapping],
        )
        assert len(config.cost_units) == 1
        assert len(config.mappings) == 1
        assert config.mapping_groups is None
        assert config.exclusions is None

    def test_configuration_full(self):
        """Test full CustomServiceConfiguration with all features."""
        # Cost units
        cost_units = [
            CustomCostUnitIn(
                name="basic-tier",
                cost="0.10",
                unit="request",
                currency="USD",
            ),
            CustomCostUnitIn(
                name="premium-tier",
                cost="0.05",
                unit="request",
                currency="USD",
            ),
        ]

        # Mappings
        mappings = [
            Mapping(
                cost_unit_switch=CostUnitSwitch(
                    field="plan",
                    cases={"premium": "premium-tier"},
                    default="basic-tier",
                ),
                field="request_count",
            ),
        ]

        # Mapping groups
        condition = Condition(equals={"path": "environment", "value": "production"})
        mapping_groups = [
            MappingGroup(
                when=condition,
                mappings=[
                    Mapping(cost_unit="production-tokens", field="usage.tokens"),
                ],
            ),
        ]

        # Exclusions
        exclusions = [
            Condition(equals={"path": "environment", "value": "test"}),
            Condition(regex={"path": "user_id", "pattern": "^bot_"}),
        ]

        config = CustomServiceConfiguration(
            cost_units=cost_units,
            mappings=mappings,
            mapping_groups=mapping_groups,
            exclusions=exclusions,
        )
        assert len(config.cost_units) == 2
        assert len(config.mappings) == 1
        assert len(config.mapping_groups) == 1
        assert len(config.exclusions) == 2

    def test_configuration_validation_missing_cost_units(self):
        """Test that configuration requires cost_units."""
        with pytest.raises(ValidationError):
            CustomServiceConfiguration(
                mappings=[Mapping(cost_unit="test", field="count")],
            )


class TestCustomServiceModels:
    """Test custom service input/output models."""

    def test_custom_service_in_valid(self):
        """Test valid CustomServiceIn creation."""
        config = CustomServiceConfiguration(
            cost_units=[
                CustomCostUnitIn(
                    name="requests",
                    cost="0.01",
                    unit="request",
                ),
            ],
            mappings=[
                Mapping(
                    cost_unit="requests",
                    field="request_count",
                ),
            ],
        )

        service = CustomServiceIn(
            custom_service_key="my-api-service",
            configuration=config,
            is_active=True,
        )
        assert service.custom_service_key == "my-api-service"
        assert service.is_active is True
        assert len(service.configuration.cost_units) == 1

    def test_custom_service_in_validation_key_required(self):
        """Test that custom_service_key is required."""
        config = CustomServiceConfiguration(
            cost_units=[CustomCostUnitIn(name="test", cost="1", unit="test")],
        )

        with pytest.raises(ValidationError):
            CustomServiceIn(
                configuration=config,
            )

    def test_custom_service_in_validation_config_required(self):
        """Test that configuration is required."""
        with pytest.raises(ValidationError):
            CustomServiceIn(
                custom_service_key="test-service",
            )

    def test_custom_service_out_valid(self):
        """Test valid CustomServiceOut creation."""
        config = CustomServiceConfiguration(
            cost_units=[
                CustomCostUnitIn(name="requests", cost="0.01", unit="request"),
            ],
        )

        cost_units_out = [
            CustomCostUnitOut(name="requests", cost="0.01", unit="request", per_quantity=1, min_units=0, max_units=10000000, currency="USD", is_active=True),
        ]

        service = CustomServiceOut(
            uuid="service-uuid",
            custom_service_key="my-api-service",
            configuration=config,
            is_active=True,
            is_deleted=False,
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
            cost_units=cost_units_out,
            team_uuid="team-uuid",
            team_name="My Team",
        )
        assert service.uuid == "service-uuid"
        assert service.custom_service_key == "my-api-service"
        assert service.team_name == "My Team"

    def test_custom_service_summary_out_valid(self):
        """Test valid CustomServiceSummaryOut creation."""
        summary = CustomServiceSummaryOut(
            uuid="service-uuid",
            custom_service_key="my-api-service",
            is_active=True,
            is_deleted=False,
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
            cost_units_count=2,
        )
        assert summary.uuid == "service-uuid"
        assert summary.cost_units_count == 2


class TestCustomServiceFilter:
    """Test custom service filter model."""

    def test_filter_empty(self):
        """Test empty filter."""
        filter_obj = CustomServiceFilter()
        assert filter_obj.is_active is None
        assert filter_obj.is_deleted is None
        assert filter_obj.has_cost_units is None

    def test_filter_with_values(self):
        """Test filter with values."""
        filter_obj = CustomServiceFilter(
            is_active=True,
            is_deleted=False,
            has_cost_units=True,
        )
        assert filter_obj.is_active is True
        assert filter_obj.is_deleted is False
        assert filter_obj.has_cost_units is True


class TestComplexExamples:
    """Test complex real-world examples from documentation."""

    def test_simple_api_pricing_example(self):
        """Test the simple API pricing example from docs."""
        config = CustomServiceConfiguration(
            cost_units=[
                CustomCostUnitIn(
                    name="requests",
                    cost="0.01",
                    unit="request",
                    per_quantity=1,
                    currency="USD",
                    is_active=True,
                ),
            ],
            mappings=[
                Mapping(
                    cost_unit="requests",
                    field="request_count",
                ),
            ],
        )

        service = CustomServiceIn(
            custom_service_key="my-api-service",
            configuration=config,
            is_active=True,
        )
        assert service.custom_service_key == "my-api-service"

    def test_token_based_llm_pricing_example(self):
        """Test the token-based LLM pricing example from docs."""
        config = CustomServiceConfiguration(
            cost_units=[
                CustomCostUnitIn(
                    name="input-tokens",
                    cost="0.001",
                    unit="token",
                    per_quantity=1000,
                    currency="USD",
                    is_active=True,
                ),
                CustomCostUnitIn(
                    name="output-tokens",
                    cost="0.002",
                    unit="token",
                    per_quantity=1000,
                    currency="USD",
                    is_active=True,
                ),
            ],
            mappings=[
                Mapping(
                    cost_unit="input-tokens",
                    field="usage.prompt_tokens",
                    divide_by=1000,
                ),
                Mapping(
                    cost_unit="output-tokens",
                    field="usage.completion_tokens",
                    divide_by=1000,
                ),
            ],
        )

        service = CustomServiceIn(
            custom_service_key="custom-llm",
            configuration=config,
            is_active=True,
        )
        assert len(service.configuration.cost_units) == 2
        assert len(service.configuration.mappings) == 2

    def test_complex_pricing_with_tiers_example(self):
        """Test the complex pricing with tiers example from docs."""
        config = CustomServiceConfiguration(
            cost_units=[
                CustomCostUnitIn(
                    name="basic-tier",
                    cost="0.10",
                    unit="request",
                    per_quantity=1,
                    currency="USD",
                    is_active=True,
                ),
                CustomCostUnitIn(
                    name="premium-tier",
                    cost="0.05",
                    unit="request",
                    per_quantity=1,
                    currency="USD",
                    is_active=True,
                ),
            ],
            mappings=[
                Mapping(
                    cost_unit_switch=CostUnitSwitch(
                        field="plan",
                        cases={"premium": "premium-tier"},
                        default="basic-tier",
                    ),
                    field="request_count",
                ),
            ],
        )

        service = CustomServiceIn(
            custom_service_key="tiered-api",
            configuration=config,
            is_active=True,
        )
        assert len(service.configuration.cost_units) == 2
        assert service.configuration.mappings[0].cost_unit_switch is not None
