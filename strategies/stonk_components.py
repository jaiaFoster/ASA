"""Pure shared Components extracted from the pinned legacy Stonk strategies.

The implementations consume ASA domain contracts only.  They contain no
provider access, legacy payload handling, portfolio policy, ranking authority,
runtime dispatch, clock access, persistence, or presentation behavior.
"""

from __future__ import annotations

import hashlib
from datetime import date
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from typing import cast

from analytics.derived_facts import (
    compute_days_to_earnings,
    compute_expiration_gap_days,
    compute_expiration_gap_distance,
    compute_forward_factor,
    compute_implied_forward_volatility,
    compute_option_volume_band,
)
from domain import (
    AnnouncementTime,
    EarningsEvent,
    EvidenceReference,
    ExpirationCollection,
    ExpirationCycle,
    OptionChain,
    OptionCollection,
    OptionContract,
    OptionLeg,
    OptionLegPosition,
    OptionStructure,
    OptionStructureType,
    OptionType,
    SecurityCollection,
)
from strategies.components import (
    BaseComponent,
    ComponentCategory,
    ComponentDefinition,
    ParameterDefinition,
    PortDefinition,
)
from strategies.errors import ComponentContractError
from strategies.manifest import ManifestObject, canonical_strategy_json
from strategies.type_system import ComponentValues, StrategyTypeReference, TypedValue

D = StrategyTypeReference("Decimal", "1.0.0")
B = StrategyTypeReference("Boolean", "1.0.0")
INTEGER = StrategyTypeReference("Integer", "1.0.0")
DATE = StrategyTypeReference("Date", "1.0.0")
EVIDENCE = StrategyTypeReference("Evidence", "1.0.0")
EVIDENCE_LIST = StrategyTypeReference("List", "1.0.0", (EVIDENCE,))
DECIMAL_LIST = StrategyTypeReference("List", "1.0.0", (D,))
OPTION_TYPE = StrategyTypeReference(
    "Enum",
    "1.0.0",
    qualifiers=ManifestObject((("values", ("call", "put")),)),
)
VERDICT = StrategyTypeReference(
    "Enum",
    "1.0.0",
    qualifiers=ManifestObject((("values", ("PASS", "WATCH", "FAIL")),)),
)
VOLUME_BAND = StrategyTypeReference(
    "Enum",
    "1.0.0",
    qualifiers=ManifestObject((("values", ("LOW", "ADEQUATE", "HIGH", "UNKNOWN")),)),
)
ANNOUNCEMENT_TIMING = StrategyTypeReference(
    "Enum",
    "1.0.0",
    qualifiers=ManifestObject((("values", tuple(item.value for item in AnnouncementTime)),)),
)
VOLUME_DOWNGRADE_REASON = StrategyTypeReference(
    "Enum",
    "1.0.0",
    qualifiers=ManifestObject(
        (("values", ("NONE", "UNKNOWN_VOLUME", "BELOW_MINIMUM_VOLUME_BAND")),)
    ),
)
SECURITY_COLLECTION = StrategyTypeReference("SecurityCollection", "1.0.0")
OPTION_CONTRACT = StrategyTypeReference("OptionContract", "1.0.0")
OPTION_COLLECTION = StrategyTypeReference("OptionCollection", "1.0.0")
OPTION_CHAIN = StrategyTypeReference("OptionChain", "1.0.0")
EXPIRATION_CYCLE = StrategyTypeReference("ExpirationCycle", "1.0.0")
EXPIRATION_COLLECTION = StrategyTypeReference("ExpirationCollection", "1.0.0")
EARNINGS_EVENT = StrategyTypeReference("EarningsEvent", "1.0.0")
OPTION_STRUCTURE = StrategyTypeReference("OptionStructure", "1.0.0")
OPTION_STRUCTURE_LIST = StrategyTypeReference("List", "1.0.0", (OPTION_STRUCTURE,))
OPTIONAL_DECIMAL = StrategyTypeReference("Optional", "1.0.0", (D,))
OPTIONAL_BOOLEAN = StrategyTypeReference("Optional", "1.0.0", (B,))
OPTIONAL_DATE = StrategyTypeReference("Optional", "1.0.0", (DATE,))
OPTIONAL_OPTION_STRUCTURE = StrategyTypeReference("Optional", "1.0.0", (OPTION_STRUCTURE,))
SKEW_DIRECTION = StrategyTypeReference(
    "Enum",
    "1.0.0",
    qualifiers=ManifestObject(
        (("values", ("BULLISH", "BEARISH", "CONFLICTING", "UNKNOWN")),)
    ),
)
FINANCIAL_DECIMAL_CONTEXT = Context(prec=34, rounding=ROUND_HALF_EVEN)


def _definition(
    namespace: str,
    name: str,
    category: ComponentCategory,
    inputs: tuple[PortDefinition, ...],
    outputs: tuple[PortDefinition, ...],
    parameters: tuple[ParameterDefinition, ...] = (),
    *,
    version: str = "1.0.0",
    algorithm_version: str = "1.0.0",
) -> ComponentDefinition:
    return ComponentDefinition(
        namespace,
        name,
        version,
        category,
        inputs,
        outputs,
        parameters,
        algorithm_version=algorithm_version,
        explanation_template=ManifestObject(
            (("migration_source", "Stonk@5f3fec8"), ("operation", name))
        ),
    )


def _parameter(parameters: ComponentValues, name: str, expected: type[object]) -> object:
    try:
        value = parameters.get(name).value
    except KeyError as exc:
        raise ComponentContractError(f"missing required parameter: {name}") from exc
    if expected is int and (isinstance(value, bool) or not isinstance(value, int)):
        raise ComponentContractError(f"parameter {name} must be Integer")
    if expected is not int and not isinstance(value, expected):
        raise ComponentContractError(f"parameter {name} has invalid type")
    return value


def _input(inputs: ComponentValues, name: str, expected: type[object]) -> object:
    try:
        value = inputs.get(name).value
    except KeyError as exc:
        raise ComponentContractError(f"missing required input: {name}") from exc
    if expected is int and (isinstance(value, bool) or not isinstance(value, int)):
        raise ComponentContractError(f"input {name} must be Integer")
    if expected is not int and not isinstance(value, expected):
        raise ComponentContractError(f"input {name} has invalid type")
    return value


def _identity(name: str, values: object) -> str:
    payload = {
        "identity_namespace": "asa.stonk.component_output",
        "identity_version": "v1",
        "component": name,
        "values": values,
    }
    return hashlib.sha256(canonical_strategy_json(payload)).hexdigest()


def _evidence(*groups: tuple[EvidenceReference, ...]) -> tuple[EvidenceReference, ...]:
    return tuple(
        sorted(
            {item for group in groups for item in group},
            key=lambda item: (item.kind.value, item.referenced_id, item.version or 0),
        )
    )


def _contract_key(value: OptionContract) -> tuple[object, ...]:
    return (
        value.expiration,
        value.strike,
        value.option_type.value,
        value.option_contract_id.scheme,
        value.option_contract_id.value,
    )


class RequiredEvidenceGate(BaseComponent):
    """True only when at least the configured number of distinct references exists."""

    __slots__ = ()
    definition = _definition(
        "asa.stonk.shared",
        "required_evidence_gate",
        ComponentCategory.PREDICATE,
        (PortDefinition("evidence", EVIDENCE_LIST),),
        (PortDefinition("complete", B),),
        (ParameterDefinition("minimum_count", INTEGER),),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        evidence = cast(tuple[EvidenceReference, ...], inputs.get("evidence").value)
        minimum = cast(int, _parameter(parameters, "minimum_count", int))
        if minimum < 1:
            raise ComponentContractError("minimum_count must be positive")
        complete = len(evidence) == len(set(evidence)) and len(evidence) >= minimum
        return ComponentValues((("complete", TypedValue(B, complete)),))


class SecurityUniverseFilter(BaseComponent):
    """Remove explicitly excluded canonical securities; no symbol inference."""

    __slots__ = ()
    definition = _definition(
        "asa.stonk.shared",
        "security_universe_filter",
        ComponentCategory.TRANSFORM,
        (
            PortDefinition("candidates", SECURITY_COLLECTION),
            PortDefinition("excluded", SECURITY_COLLECTION),
        ),
        (PortDefinition("included", SECURITY_COLLECTION),),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        candidates = cast(SecurityCollection, _input(inputs, "candidates", SecurityCollection))
        excluded = cast(SecurityCollection, _input(inputs, "excluded", SecurityCollection))
        excluded_ids = {item.instrument.identity for item in excluded.securities}
        result = SecurityCollection(
            tuple(
                item
                for item in candidates.securities
                if item.instrument.identity not in excluded_ids
            )
        )
        return ComponentValues((("included", TypedValue(SECURITY_COLLECTION, result)),))


class DeterministicSecurityCap(BaseComponent):
    """Apply a stable cap after canonical SecurityCollection ordering."""

    __slots__ = ()
    definition = _definition(
        "asa.stonk.shared",
        "deterministic_security_cap",
        ComponentCategory.TRANSFORM,
        (PortDefinition("candidates", SECURITY_COLLECTION),),
        (PortDefinition("selected", SECURITY_COLLECTION),),
        (ParameterDefinition("maximum_count", INTEGER),),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        candidates = cast(SecurityCollection, _input(inputs, "candidates", SecurityCollection))
        maximum = cast(int, _parameter(parameters, "maximum_count", int))
        if maximum < 1:
            raise ComponentContractError("maximum_count must be positive")
        result = SecurityCollection(candidates.securities[:maximum])
        return ComponentValues((("selected", TypedValue(SECURITY_COLLECTION, result)),))


class WeightedScoreWithCeiling(BaseComponent):
    """Weighted mean with an explicit deterministic upper ceiling."""

    __slots__ = ()
    definition = _definition(
        "asa.stonk.shared",
        "weighted_score_with_ceiling",
        ComponentCategory.SCORE,
        (PortDefinition("values", DECIMAL_LIST), PortDefinition("weights", DECIMAL_LIST)),
        (PortDefinition("score", D),),
        (ParameterDefinition("ceiling", D),),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        values = cast(tuple[Decimal, ...], inputs.get("values").value)
        weights = cast(tuple[Decimal, ...], inputs.get("weights").value)
        ceiling = cast(Decimal, _parameter(parameters, "ceiling", Decimal))
        if len(values) != len(weights) or not values:
            raise ComponentContractError("score requires aligned non-empty values and weights")
        total_weight = sum(weights, Decimal(0))
        if total_weight <= 0 or any(weight < 0 for weight in weights):
            raise ComponentContractError("score weights must be non-negative with positive sum")
        score = (
            sum(
                (value * weight for value, weight in zip(values, weights, strict=True)),
                Decimal(0),
            )
            / total_weight
        )
        return ComponentValues((("score", TypedValue(D, min(score, ceiling))),))


class TwoFactorWeightedScore(BaseComponent):
    """Named two-factor weighted score with explicit manifest policy."""

    __slots__ = ()
    definition = _definition(
        "asa.stonk.shared",
        "two_factor_weighted_score",
        ComponentCategory.SCORE,
        (
            PortDefinition("primary", D),
            PortDefinition("secondary", D),
        ),
        (
            PortDefinition("primary", D),
            PortDefinition("secondary", D),
            PortDefinition("score", D),
        ),
        (
            ParameterDefinition("primary_weight", D),
            ParameterDefinition("secondary_weight", D),
            ParameterDefinition("ceiling", D),
        ),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        primary = cast(Decimal, _input(inputs, "primary", Decimal))
        secondary = cast(Decimal, _input(inputs, "secondary", Decimal))
        primary_weight = cast(Decimal, _parameter(parameters, "primary_weight", Decimal))
        secondary_weight = cast(Decimal, _parameter(parameters, "secondary_weight", Decimal))
        ceiling = cast(Decimal, _parameter(parameters, "ceiling", Decimal))
        total_weight = primary_weight + secondary_weight
        if min(primary_weight, secondary_weight) < 0 or total_weight <= 0:
            raise ComponentContractError("factor weights must be non-negative with positive sum")
        score = (primary * primary_weight + secondary * secondary_weight) / total_weight
        return ComponentValues(
            (
                ("primary", TypedValue(D, primary)),
                ("score", TypedValue(D, min(score, ceiling))),
                ("secondary", TypedValue(D, secondary)),
            )
        )


class VerdictClassifier(BaseComponent):
    """Map a score to a manifest-configured tier; never ranks candidates."""

    __slots__ = ()
    definition = _definition(
        "asa.stonk.shared",
        "verdict_classifier",
        ComponentCategory.PREDICATE,
        (PortDefinition("score", D),),
        (PortDefinition("verdict", VERDICT),),
        (
            ParameterDefinition("pass_threshold", D),
            ParameterDefinition("watch_threshold", D),
        ),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        score = cast(Decimal, inputs.get("score").value)
        pass_threshold = cast(Decimal, _parameter(parameters, "pass_threshold", Decimal))
        watch_threshold = cast(Decimal, _parameter(parameters, "watch_threshold", Decimal))
        if watch_threshold > pass_threshold:
            raise ComponentContractError("watch_threshold cannot exceed pass_threshold")
        verdict = (
            "PASS" if score >= pass_threshold else "WATCH" if score >= watch_threshold else "FAIL"
        )
        return ComponentValues((("verdict", TypedValue(VERDICT, verdict)),))


class VerdictEligibilityGate(BaseComponent):
    """Force FAIL when a manifest eligibility path rejects a candidate."""

    __slots__ = ()
    definition = _definition(
        "asa.stonk.shared",
        "verdict_eligibility_gate",
        ComponentCategory.PREDICATE,
        (
            PortDefinition("verdict", VERDICT),
            PortDefinition("eligible", B),
        ),
        (PortDefinition("verdict", VERDICT),),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        verdict = cast(str, inputs.get("verdict").value)
        eligible = cast(bool, inputs.get("eligible").value)
        return ComponentValues((("verdict", TypedValue(VERDICT, verdict if eligible else "FAIL")),))


class VerdictEligibilitySupplementGate(BaseComponent):
    """Apply hard eligibility and downgrade weak supplemental evidence to WATCH."""

    __slots__ = ()
    definition = _definition(
        "asa.stonk.shared",
        "verdict_eligibility_supplement_gate",
        ComponentCategory.PREDICATE,
        (
            PortDefinition("verdict", VERDICT),
            PortDefinition("eligible", B),
            PortDefinition("supplement_strong", B),
        ),
        (PortDefinition("verdict", VERDICT),),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        verdict = cast(str, inputs.get("verdict").value)
        eligible = cast(bool, inputs.get("eligible").value)
        supplement_strong = cast(bool, inputs.get("supplement_strong").value)
        if not eligible:
            result = "FAIL"
        elif verdict == "PASS" and not supplement_strong:
            result = "WATCH"
        else:
            result = verdict
        return ComponentValues((("verdict", TypedValue(VERDICT, result)),))


class EarningsEventWindow(BaseComponent):
    """Evaluate the preferred front-before-event/back-after-event window."""

    __slots__ = ()
    definition = _definition(
        "asa.stonk.options",
        "earnings_event_window",
        ComponentCategory.PREDICATE,
        (
            PortDefinition("event", EARNINGS_EVENT),
            PortDefinition("front", EXPIRATION_CYCLE),
            PortDefinition("back", EXPIRATION_CYCLE),
        ),
        (PortDefinition("eligible", B),),
        (ParameterDefinition("require_confirmed", B),),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        event = cast(EarningsEvent, _input(inputs, "event", EarningsEvent))
        front = cast(ExpirationCycle, _input(inputs, "front", ExpirationCycle))
        back = cast(ExpirationCycle, _input(inputs, "back", ExpirationCycle))
        require_confirmed = cast(bool, _parameter(parameters, "require_confirmed", bool))
        if front.as_of != back.as_of:
            raise ComponentContractError("expiration cycles must share as_of")
        front_before = front.expiration_date < event.earnings_date
        if (
            front.expiration_date == event.earnings_date
            and event.announcement_time is AnnouncementTime.AFTER_CLOSE
        ):
            front_before = True
        eligible = (
            front_before
            and event.earnings_date < back.expiration_date
            and (event.confirmed or not require_confirmed)
        )
        return ComponentValues((("eligible", TypedValue(B, eligible)),))


class EarningsEventProjection(BaseComponent):
    """Expose event facts and canonical days-to-event derived evidence."""

    __slots__ = ()
    definition = _definition(
        "asa.stonk.options",
        "earnings_event_projection",
        ComponentCategory.TRANSFORM,
        (PortDefinition("event", EARNINGS_EVENT), PortDefinition("as_of", DATE)),
        (
            PortDefinition("earnings_date", DATE),
            PortDefinition("days_to_earnings", INTEGER),
            PortDefinition("announcement_timing", ANNOUNCEMENT_TIMING),
        ),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        event = cast(EarningsEvent, _input(inputs, "event", EarningsEvent))
        as_of = cast(date, _input(inputs, "as_of", date))
        return ComponentValues(
            (
                (
                    "announcement_timing",
                    TypedValue(ANNOUNCEMENT_TIMING, event.announcement_time.value),
                ),
                (
                    "days_to_earnings",
                    TypedValue(INTEGER, compute_days_to_earnings(as_of, event.earnings_date)),
                ),
                ("earnings_date", TypedValue(DATE, event.earnings_date)),
            )
        )


class ForwardFactorEligibilityGate(BaseComponent):
    """Expose each hard gate while preserving existing aggregate eligibility."""

    __slots__ = ()
    definition = _definition(
        "asa.stonk.options",
        "forward_factor_eligibility_gate",
        ComponentCategory.PREDICATE,
        (
            PortDefinition("earnings_eligible", B),
            PortDefinition("structures", OPTION_STRUCTURE_LIST),
            PortDefinition("liquidity_acceptable", B),
            PortDefinition("confirmed_earnings_date", OPTIONAL_DATE),
        ),
        (
            PortDefinition("earnings_exclusion_gate", B),
            PortDefinition("structure_constructible_gate", B),
            PortDefinition("liquidity_gate", B),
            PortDefinition("eligible", B),
            PortDefinition("confirmed_earnings_date", OPTIONAL_DATE),
        ),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        earnings_gate = cast(bool, inputs.get("earnings_eligible").value)
        structures = cast(tuple[OptionStructure, ...], inputs.get("structures").value)
        liquidity_gate = cast(bool, inputs.get("liquidity_acceptable").value)
        structure_gate = bool(structures)
        return ComponentValues(
            (
                ("confirmed_earnings_date", inputs.get("confirmed_earnings_date")),
                ("earnings_exclusion_gate", TypedValue(B, earnings_gate)),
                ("eligible", TypedValue(B, earnings_gate and structure_gate and liquidity_gate)),
                ("liquidity_gate", TypedValue(B, liquidity_gate)),
                ("structure_constructible_gate", TypedValue(B, structure_gate)),
            )
        )


class ExpirationPairSelector(BaseComponent):
    """Select one stable preferred event-spanning expiration pair."""

    __slots__ = ()
    definition = _definition(
        "asa.stonk.options",
        "expiration_pair_selector",
        ComponentCategory.TRANSFORM,
        (
            PortDefinition("expirations", EXPIRATION_COLLECTION),
            PortDefinition("event", EARNINGS_EVENT),
        ),
        (
            PortDefinition("selected", EXPIRATION_COLLECTION),
            PortDefinition("gap_eligible", B),
        ),
        (
            ParameterDefinition("front_min_dte", INTEGER),
            ParameterDefinition("front_max_dte", INTEGER),
            ParameterDefinition("back_min_dte", INTEGER),
            ParameterDefinition("back_max_dte", INTEGER),
            ParameterDefinition("target_gap_days", INTEGER),
            ParameterDefinition("gap_tolerance_days", INTEGER),
        ),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        expirations = cast(
            ExpirationCollection, _input(inputs, "expirations", ExpirationCollection)
        )
        event = cast(EarningsEvent, _input(inputs, "event", EarningsEvent))
        bounds = {
            name: cast(int, _parameter(parameters, name, int))
            for name in (
                "front_min_dte",
                "front_max_dte",
                "back_min_dte",
                "back_max_dte",
                "target_gap_days",
                "gap_tolerance_days",
            )
        }
        if (
            min(bounds.values()) < 0
            or bounds["front_min_dte"] > bounds["front_max_dte"]
            or bounds["back_min_dte"] > bounds["back_max_dte"]
        ):
            raise ComponentContractError("expiration DTE bounds are invalid")
        fronts = tuple(
            item
            for item in expirations.cycles
            if bounds["front_min_dte"] <= item.days_to_expiration <= bounds["front_max_dte"]
            and (
                item.expiration_date < event.earnings_date
                or (
                    item.expiration_date == event.earnings_date
                    and event.announcement_time is AnnouncementTime.AFTER_CLOSE
                )
            )
        )
        backs = tuple(
            item
            for item in expirations.cycles
            if bounds["back_min_dte"] <= item.days_to_expiration <= bounds["back_max_dte"]
            and item.expiration_date > event.earnings_date
        )
        pairs = tuple(
            (front, back)
            for front in fronts
            for back in backs
            if back.expiration_date > front.expiration_date
            and compute_expiration_gap_distance(
                front.expiration_date,
                back.expiration_date,
                bounds["target_gap_days"],
            )
            <= bounds["gap_tolerance_days"]
        )
        selected = min(
            pairs,
            key=lambda pair: (
                compute_expiration_gap_distance(
                    pair[0].expiration_date,
                    pair[1].expiration_date,
                    bounds["target_gap_days"],
                ),
                (event.earnings_date - pair[0].expiration_date).days
                + (pair[1].expiration_date - event.earnings_date).days,
                pair[0].expiration_date,
                pair[1].expiration_date,
            ),
            default=None,
        )
        result = ExpirationCollection(expirations.as_of, selected or ())
        return ComponentValues(
            (
                ("gap_eligible", TypedValue(B, selected is not None)),
                ("selected", TypedValue(EXPIRATION_COLLECTION, result)),
            )
        )


class DtePairSelector(BaseComponent):
    """Select one stable front/back pair from explicit DTE and gap policy."""

    __slots__ = ()
    definition = _definition(
        "asa.stonk.options",
        "dte_pair_selector",
        ComponentCategory.TRANSFORM,
        (PortDefinition("expirations", EXPIRATION_COLLECTION),),
        (PortDefinition("selected", EXPIRATION_COLLECTION),),
        (
            ParameterDefinition("front_min_dte", INTEGER),
            ParameterDefinition("front_max_dte", INTEGER),
            ParameterDefinition("back_min_dte", INTEGER),
            ParameterDefinition("back_max_dte", INTEGER),
            ParameterDefinition("minimum_gap_days", INTEGER),
            ParameterDefinition("maximum_gap_days", INTEGER),
            ParameterDefinition("target_front_dte", INTEGER),
            ParameterDefinition("target_gap_days", INTEGER),
        ),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        expirations = cast(
            ExpirationCollection, _input(inputs, "expirations", ExpirationCollection)
        )
        policy = {
            name: cast(int, _parameter(parameters, name, int))
            for name in (
                "front_min_dte",
                "front_max_dte",
                "back_min_dte",
                "back_max_dte",
                "minimum_gap_days",
                "maximum_gap_days",
                "target_front_dte",
                "target_gap_days",
            )
        }
        if (
            min(policy.values()) < 0
            or policy["front_min_dte"] > policy["front_max_dte"]
            or policy["back_min_dte"] > policy["back_max_dte"]
            or policy["minimum_gap_days"] > policy["maximum_gap_days"]
        ):
            raise ComponentContractError("DTE pair policy is invalid")
        pairs = tuple(
            (front, back)
            for front in expirations.cycles
            for back in expirations.cycles
            if policy["front_min_dte"] <= front.days_to_expiration <= policy["front_max_dte"]
            and policy["back_min_dte"] <= back.days_to_expiration <= policy["back_max_dte"]
            and policy["minimum_gap_days"]
            <= back.days_to_expiration - front.days_to_expiration
            <= policy["maximum_gap_days"]
        )
        selected = min(
            pairs,
            key=lambda pair: (
                abs(pair[0].days_to_expiration - policy["target_front_dte"])
                + abs(
                    pair[1].days_to_expiration
                    - pair[0].days_to_expiration
                    - policy["target_gap_days"]
                ),
                pair[0].expiration_date,
                pair[1].expiration_date,
            ),
            default=None,
        )
        result = ExpirationCollection(expirations.as_of, selected or ())
        return ComponentValues((("selected", TypedValue(EXPIRATION_COLLECTION, result)),))


class ExpirationPairProjection(BaseComponent):
    """Project an exact selected pair into typed front/back dates."""

    __slots__ = ()
    definition = _definition(
        "asa.stonk.options",
        "expiration_pair_projection",
        ComponentCategory.TRANSFORM,
        (PortDefinition("selected", EXPIRATION_COLLECTION),),
        (PortDefinition("front_expiration", DATE), PortDefinition("back_expiration", DATE)),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        selected = cast(ExpirationCollection, _input(inputs, "selected", ExpirationCollection))
        if len(selected.cycles) != 2:
            raise ComponentContractError("expiration pair projection requires exactly two cycles")
        front, back = selected.cycles
        return ComponentValues(
            (
                ("back_expiration", TypedValue(DATE, back.expiration_date)),
                ("front_expiration", TypedValue(DATE, front.expiration_date)),
            )
        )


class ExpirationGapProjection(BaseComponent):
    """Expose canonical actual and target-deviation gap derived facts."""

    __slots__ = ()
    definition = _definition(
        "asa.stonk.options",
        "expiration_gap_projection",
        ComponentCategory.TRANSFORM,
        (PortDefinition("selected", EXPIRATION_COLLECTION),),
        (
            PortDefinition("actual_gap_days", INTEGER),
            PortDefinition("gap_deviation_days", INTEGER),
        ),
        (ParameterDefinition("target_gap_days", INTEGER),),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        selected = cast(ExpirationCollection, _input(inputs, "selected", ExpirationCollection))
        if len(selected.cycles) != 2:
            raise ComponentContractError("expiration gap projection requires exactly two cycles")
        front, back = selected.cycles
        target_gap_days = cast(int, _parameter(parameters, "target_gap_days", int))
        actual_gap_days = compute_expiration_gap_days(front.expiration_date, back.expiration_date)
        gap_deviation_days = compute_expiration_gap_distance(
            front.expiration_date, back.expiration_date, target_gap_days
        )
        return ComponentValues(
            (
                ("actual_gap_days", TypedValue(INTEGER, actual_gap_days)),
                ("gap_deviation_days", TypedValue(INTEGER, gap_deviation_days)),
            )
        )


class ForwardFactor(BaseComponent):
    """Compute raw front IV divided by forward IV minus one."""

    __slots__ = ()
    definition = _definition(
        "asa.stonk.options",
        "forward_factor",
        ComponentCategory.SCORE,
        (
            PortDefinition("front_iv", D),
            PortDefinition("implied_forward_iv", D),
        ),
        (
            PortDefinition("factor", D),
            PortDefinition("front_iv", D),
        ),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        front = cast(Decimal, _input(inputs, "front_iv", Decimal))
        forward = cast(Decimal, _input(inputs, "implied_forward_iv", Decimal))
        try:
            factor = compute_forward_factor(front, forward)
        except ValueError as exc:
            raise ComponentContractError(
                "forward factor requires non-negative front IV and positive forward IV"
            ) from exc
        return ComponentValues(
            (
                ("factor", TypedValue(D, factor)),
                ("front_iv", TypedValue(D, front)),
            )
        )


class ImpliedForwardVolatility(BaseComponent):
    """Derive annualized forward volatility from explicit IV and DTE inputs."""

    __slots__ = ()
    definition = _definition(
        "asa.stonk.options",
        "implied_forward_volatility",
        ComponentCategory.TRANSFORM,
        (
            PortDefinition("front_iv", D),
            PortDefinition("back_iv", D),
            PortDefinition("front_dte", INTEGER),
            PortDefinition("back_dte", INTEGER),
        ),
        (PortDefinition("implied_forward_iv", D),),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        front_iv = cast(Decimal, _input(inputs, "front_iv", Decimal))
        back_iv = cast(Decimal, _input(inputs, "back_iv", Decimal))
        front_dte = cast(int, _input(inputs, "front_dte", int))
        back_dte = cast(int, _input(inputs, "back_dte", int))
        if not (Decimal(0) < front_iv <= Decimal(5)) or not (Decimal(0) < back_iv <= Decimal(5)):
            raise ComponentContractError("IV inputs must be annualized decimal ratios")
        try:
            with localcontext(FINANCIAL_DECIMAL_CONTEXT):
                forward_iv = compute_implied_forward_volatility(
                    front_iv, back_iv, front_dte, back_dte
                )
        except ValueError as exc:
            raise ComponentContractError(
                "back DTE and implied forward variance must be valid"
            ) from exc
        return ComponentValues((("implied_forward_iv", TypedValue(D, forward_iv)),))


class OptionLegLiquidity(BaseComponent):
    """Evaluate quote width, open interest, and volume without deriving a mark."""

    __slots__ = ()
    definition = _definition(
        "asa.stonk.options",
        "option_leg_liquidity",
        ComponentCategory.PREDICATE,
        (PortDefinition("contract", OPTION_CONTRACT),),
        (PortDefinition("liquid", B),),
        (
            ParameterDefinition("maximum_spread_ratio", D),
            ParameterDefinition("minimum_open_interest", INTEGER),
            ParameterDefinition("minimum_volume", INTEGER),
        ),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        contract = cast(OptionContract, _input(inputs, "contract", OptionContract))
        maximum_spread = cast(Decimal, _parameter(parameters, "maximum_spread_ratio", Decimal))
        minimum_oi = cast(int, _parameter(parameters, "minimum_open_interest", int))
        minimum_volume = cast(int, _parameter(parameters, "minimum_volume", int))
        if maximum_spread < 0 or minimum_oi < 0 or minimum_volume < 0:
            raise ComponentContractError("liquidity thresholds cannot be negative")
        liquid = False
        if (
            contract.bid is not None
            and contract.ask is not None
            and contract.mark is not None
            and contract.mark > 0
            and contract.open_interest is not None
            and contract.volume is not None
        ):
            spread = (contract.ask - contract.bid) / contract.mark
            liquid = (
                spread <= maximum_spread
                and contract.open_interest >= minimum_oi
                and contract.volume >= minimum_volume
            )
        return ComponentValues((("liquid", TypedValue(B, liquid)),))


def _nearest_delta(
    contracts: tuple[OptionContract, ...],
    expiration: date,
    option_type: OptionType,
    target: Decimal,
    *,
    excluded: frozenset[str] = frozenset(),
) -> OptionContract:
    choices = tuple(
        item
        for item in contracts
        if item.expiration == expiration
        and item.option_type is option_type
        and item.delta is not None
        and item.identity not in excluded
    )
    if not choices:
        raise ComponentContractError("no option contract matches delta-selection inputs")
    return min(
        choices,
        key=lambda item: (abs(abs(cast(Decimal, item.delta)) - abs(target)), _contract_key(item)),
    )


def _vertical(
    chain: OptionChain,
    expiration: date,
    option_type: OptionType,
    long_target: Decimal,
    short_target: Decimal,
) -> OptionStructure:
    long_contract = _nearest_delta(chain.contracts, expiration, option_type, long_target)
    short_contract = _nearest_delta(
        chain.contracts,
        expiration,
        option_type,
        short_target,
        excluded=frozenset({long_contract.identity}),
    )
    return OptionStructure(
        _identity(
            "vertical_structure",
            [long_contract.observation_identity, short_contract.observation_identity],
        ),
        OptionStructureType.VERTICAL,
        chain.underlying,
        (
            OptionLeg(long_contract, OptionLegPosition.LONG, Decimal(1), "long"),
            OptionLeg(short_contract, OptionLegPosition.SHORT, Decimal(1), "short"),
        ),
        chain.observed_at,
        _evidence(chain.evidence, long_contract.evidence, short_contract.evidence),
    )


class DeltaNearestLeg(BaseComponent):
    """Select the nearest absolute delta with a stable contract tie-breaker."""

    __slots__ = ()
    definition = _definition(
        "asa.stonk.options",
        "delta_nearest_leg",
        ComponentCategory.TRANSFORM,
        (PortDefinition("contracts", OPTION_COLLECTION), PortDefinition("expiration", DATE)),
        (PortDefinition("contract", OPTION_CONTRACT),),
        (
            ParameterDefinition("option_type", OPTION_TYPE),
            ParameterDefinition("target_delta", D),
        ),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        contracts = cast(OptionCollection, _input(inputs, "contracts", OptionCollection)).contracts
        expiration = cast(date, _input(inputs, "expiration", date))
        option_type = OptionType(cast(str, _parameter(parameters, "option_type", str)))
        target = cast(Decimal, _parameter(parameters, "target_delta", Decimal))
        selected = _nearest_delta(contracts, expiration, option_type, target)
        return ComponentValues((("contract", TypedValue(OPTION_CONTRACT, selected)),))


def _nearest_common_strike_delta(
    chain: OptionChain,
    front: date,
    back: date,
    option_type: OptionType,
    target: Decimal,
) -> OptionContract | None:
    """Select the nearest front delta only among uniquely constructible calendars."""

    choices = tuple(
        item
        for item in chain.find(expiration=front, option_type=option_type)
        if item.delta is not None
        and len(
            chain.find(
                expiration=front,
                option_type=option_type,
                strike=item.strike,
            )
        )
        == 1
        and len(
            chain.find(
                expiration=back,
                option_type=option_type,
                strike=item.strike,
            )
        )
        == 1
    )
    return min(
        choices,
        key=lambda item: (
            abs(abs(cast(Decimal, item.delta)) - abs(target)),
            _contract_key(item),
        ),
        default=None,
    )


def _same_strike(
    chain: OptionChain,
    expiration: date,
    option_type: OptionType,
    strike: Decimal,
) -> OptionContract:
    matches = chain.find(expiration=expiration, option_type=option_type, strike=strike)
    if len(matches) != 1:
        raise ComponentContractError("expected exactly one matching option contract")
    return matches[0]


def _calendar(
    chain: OptionChain,
    front: date,
    back: date,
    option_type: OptionType,
    strike: Decimal,
    role_suffix: str = "",
) -> OptionStructure:
    short_front = _same_strike(chain, front, option_type, strike)
    long_back = _same_strike(chain, back, option_type, strike)
    structure_id = _identity(
        "calendar_structure",
        [short_front.observation_identity, long_back.observation_identity, role_suffix],
    )
    suffix = f"_{role_suffix}" if role_suffix else ""
    return OptionStructure(
        structure_id,
        OptionStructureType.CALENDAR,
        chain.underlying,
        (
            OptionLeg(short_front, OptionLegPosition.SHORT, Decimal(1), f"short_front{suffix}"),
            OptionLeg(long_back, OptionLegPosition.LONG, Decimal(1), f"long_back{suffix}"),
        ),
        chain.observed_at,
        _evidence(chain.evidence, short_front.evidence, long_back.evidence),
    )


class CalendarStructure(BaseComponent):
    __slots__ = ()
    definition = _definition(
        "asa.stonk.options",
        "calendar_structure",
        ComponentCategory.TRANSFORM,
        (
            PortDefinition("chain", OPTION_CHAIN),
            PortDefinition("front_expiration", DATE),
            PortDefinition("back_expiration", DATE),
            PortDefinition("strike", D),
        ),
        (PortDefinition("structure", OPTION_STRUCTURE),),
        (ParameterDefinition("option_type", OPTION_TYPE),),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        chain = cast(OptionChain, _input(inputs, "chain", OptionChain))
        front = cast(date, _input(inputs, "front_expiration", date))
        back = cast(date, _input(inputs, "back_expiration", date))
        strike = cast(Decimal, _input(inputs, "strike", Decimal))
        option_type = OptionType(cast(str, _parameter(parameters, "option_type", str)))
        structure = _calendar(chain, front, back, option_type, strike)
        return ComponentValues((("structure", TypedValue(OPTION_STRUCTURE, structure)),))


class NearestCommonStrikeCalendar(BaseComponent):
    """Choose the common strike nearest an explicit target and build a calendar."""

    __slots__ = ()
    definition = _definition(
        "asa.stonk.options",
        "nearest_common_strike_calendar",
        ComponentCategory.TRANSFORM,
        (
            PortDefinition("chain", OPTION_CHAIN),
            PortDefinition("front_expiration", DATE),
            PortDefinition("back_expiration", DATE),
            PortDefinition("target_strike", D),
        ),
        (PortDefinition("structure", OPTION_STRUCTURE),),
        (ParameterDefinition("option_type", OPTION_TYPE),),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        chain = cast(OptionChain, _input(inputs, "chain", OptionChain))
        front = cast(date, _input(inputs, "front_expiration", date))
        back = cast(date, _input(inputs, "back_expiration", date))
        target = cast(Decimal, _input(inputs, "target_strike", Decimal))
        option_type = OptionType(cast(str, _parameter(parameters, "option_type", str)))
        front_strikes = {
            item.strike for item in chain.find(expiration=front, option_type=option_type)
        }
        back_strikes = {
            item.strike for item in chain.find(expiration=back, option_type=option_type)
        }
        common = front_strikes & back_strikes
        if not common:
            raise ComponentContractError("no common strike exists for calendar inputs")
        strike = min(common, key=lambda value: (abs(value - target), value))
        structure = _calendar(chain, front, back, option_type, strike)
        return ComponentValues((("structure", TypedValue(OPTION_STRUCTURE, structure)),))


class VerticalStructure(BaseComponent):
    __slots__ = ()
    definition = _definition(
        "asa.stonk.options",
        "vertical_structure",
        ComponentCategory.TRANSFORM,
        (PortDefinition("chain", OPTION_CHAIN), PortDefinition("expiration", DATE)),
        (PortDefinition("structure", OPTION_STRUCTURE),),
        (
            ParameterDefinition("option_type", OPTION_TYPE),
            ParameterDefinition("long_delta_target", D),
            ParameterDefinition("short_delta_target", D),
        ),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        chain = cast(OptionChain, _input(inputs, "chain", OptionChain))
        expiration = cast(date, _input(inputs, "expiration", date))
        option_type = OptionType(cast(str, _parameter(parameters, "option_type", str)))
        long_target = cast(Decimal, _parameter(parameters, "long_delta_target", Decimal))
        short_target = cast(Decimal, _parameter(parameters, "short_delta_target", Decimal))
        structure = _vertical(chain, expiration, option_type, long_target, short_target)
        return ComponentValues((("structure", TypedValue(OPTION_STRUCTURE, structure)),))


class SkewMomentumResearchDecision(BaseComponent):
    """Versioned two-sided research policy; UNKNOWN evidence never uses a proxy."""

    __slots__ = ()
    definition = _definition(
        "asa.stonk.options",
        "skew_momentum_research_decision",
        ComponentCategory.PREDICATE,
        (
            PortDefinition("chain", OPTION_CHAIN),
            PortDefinition("expiration", DATE),
            PortDefinition("normalized_call_skew", D),
            PortDefinition("normalized_put_skew", D),
            PortDefinition("call_skew_zscore", OPTIONAL_DECIMAL),
            PortDefinition("put_skew_zscore", OPTIONAL_DECIMAL),
            PortDefinition("historical_valid_observations", INTEGER),
            PortDefinition("call_atm_iv_minus_rv", D),
            PortDefinition("put_atm_iv_minus_rv", D),
            PortDefinition("call_wing_iv_minus_rv", D),
            PortDefinition("put_wing_iv_minus_rv", D),
            PortDefinition("call_wing_iv_minus_atm_iv", D),
            PortDefinition("put_wing_iv_minus_atm_iv", D),
            PortDefinition("time_series_return", D),
            PortDefinition("cross_sectional_percentile", OPTIONAL_DECIMAL),
            PortDefinition("comparison_peer_count", INTEGER),
            PortDefinition("sector_relative_return", OPTIONAL_DECIMAL),
        ),
        (
            PortDefinition("verdict", VERDICT),
            PortDefinition("direction", SKEW_DIRECTION),
            PortDefinition("structure", OPTIONAL_OPTION_STRUCTURE),
            PortDefinition("score", D),
            PortDefinition("bullish_core_gate", OPTIONAL_BOOLEAN),
            PortDefinition("bearish_core_gate", OPTIONAL_BOOLEAN),
            PortDefinition("liquidity_acceptable", B),
            PortDefinition("momentum_alignment_count", INTEGER),
            PortDefinition("momentum_complete", B),
            PortDefinition("normalized_call_skew", D),
            PortDefinition("normalized_put_skew", D),
            PortDefinition("call_skew_zscore", OPTIONAL_DECIMAL),
            PortDefinition("put_skew_zscore", OPTIONAL_DECIMAL),
            PortDefinition("historical_valid_observations", INTEGER),
            PortDefinition("call_atm_iv_minus_rv", D),
            PortDefinition("put_atm_iv_minus_rv", D),
            PortDefinition("call_wing_iv_minus_rv", D),
            PortDefinition("put_wing_iv_minus_rv", D),
            PortDefinition("call_wing_iv_minus_atm_iv", D),
            PortDefinition("put_wing_iv_minus_atm_iv", D),
            PortDefinition("time_series_return", D),
            PortDefinition("cross_sectional_percentile", OPTIONAL_DECIMAL),
            PortDefinition("comparison_peer_count", INTEGER),
            PortDefinition("sector_relative_return", OPTIONAL_DECIMAL),
            PortDefinition("mid_debit", OPTIONAL_DECIMAL),
            PortDefinition("conservative_debit", OPTIONAL_DECIMAL),
        ),
        (
            ParameterDefinition("skew_zscore_threshold", D),
            ParameterDefinition("historical_lookback_observations", INTEGER),
            ParameterDefinition("minimum_valid_observations", INTEGER),
            ParameterDefinition("time_series_lookback_sessions", INTEGER),
            ParameterDefinition("bullish_cross_sectional_minimum", D),
            ParameterDefinition("bearish_cross_sectional_maximum", D),
            ParameterDefinition("required_momentum_alignment", INTEGER),
            ParameterDefinition("long_delta_target", D),
            ParameterDefinition("short_delta_target", D),
            ParameterDefinition("maximum_spread_ratio", D),
            ParameterDefinition("minimum_open_interest", INTEGER),
            ParameterDefinition("minimum_volume", INTEGER),
        ),
        version="1.0.1",
        algorithm_version="1.0.1",
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        chain = cast(OptionChain, _input(inputs, "chain", OptionChain))
        expiration = cast(date, _input(inputs, "expiration", date))

        def decimal(name: str) -> Decimal:
            return cast(Decimal, _input(inputs, name, Decimal))

        def optional_decimal(name: str) -> Decimal | None:
            value = inputs.get(name).value
            if value is not None and not isinstance(value, Decimal):
                raise ComponentContractError(f"input {name} must be Optional[Decimal]")
            return value

        threshold = cast(Decimal, _parameter(parameters, "skew_zscore_threshold", Decimal))
        bullish_cross_min = cast(
            Decimal, _parameter(parameters, "bullish_cross_sectional_minimum", Decimal)
        )
        bearish_cross_max = cast(
            Decimal, _parameter(parameters, "bearish_cross_sectional_maximum", Decimal)
        )
        required_alignment = cast(
            int, _parameter(parameters, "required_momentum_alignment", int)
        )
        historical_lookback = cast(
            int, _parameter(parameters, "historical_lookback_observations", int)
        )
        minimum_history = cast(
            int, _parameter(parameters, "minimum_valid_observations", int)
        )
        time_series_lookback = cast(
            int, _parameter(parameters, "time_series_lookback_sessions", int)
        )
        long_target = cast(Decimal, _parameter(parameters, "long_delta_target", Decimal))
        short_target = cast(Decimal, _parameter(parameters, "short_delta_target", Decimal))
        maximum_spread = cast(
            Decimal, _parameter(parameters, "maximum_spread_ratio", Decimal)
        )
        minimum_oi = cast(int, _parameter(parameters, "minimum_open_interest", int))
        minimum_volume = cast(int, _parameter(parameters, "minimum_volume", int))
        if (
            not Decimal(0) <= bearish_cross_max <= bullish_cross_min <= Decimal(1)
            or required_alignment != 2
            or historical_lookback != 60
            or minimum_history != 40
            or time_series_lookback != 20
            or maximum_spread < 0
            or min(minimum_oi, minimum_volume) < 0
        ):
            raise ComponentContractError("Skew Momentum research policy is invalid")

        historical_valid_observations = cast(
            int, _input(inputs, "historical_valid_observations", int)
        )
        call_zscore = (
            optional_decimal("call_skew_zscore")
            if historical_valid_observations >= minimum_history
            else None
        )
        put_zscore = (
            optional_decimal("put_skew_zscore")
            if historical_valid_observations >= minimum_history
            else None
        )
        call_value_gate = (
            decimal("call_atm_iv_minus_rv") <= 0
            and decimal("call_wing_iv_minus_rv") > 0
            and decimal("call_wing_iv_minus_atm_iv") > 0
        )
        put_value_gate = (
            decimal("put_atm_iv_minus_rv") <= 0
            and decimal("put_wing_iv_minus_rv") > 0
            and decimal("put_wing_iv_minus_atm_iv") > 0
        )
        bullish_core = (
            False
            if not call_value_gate
            else None
            if call_zscore is None
            else call_zscore <= threshold
        )
        bearish_core = (
            False
            if not put_value_gate
            else None
            if put_zscore is None
            else put_zscore <= threshold
        )

        direction = "UNKNOWN"
        structure: OptionStructure | None = None
        if bullish_core is True and bearish_core is True:
            direction = "CONFLICTING"
        elif bullish_core is True:
            direction = "BULLISH"
            structure = _vertical(
                chain, expiration, OptionType.CALL, long_target, short_target
            )
        elif bearish_core is True:
            direction = "BEARISH"
            structure = _vertical(
                chain, expiration, OptionType.PUT, long_target, short_target
            )

        time_series_return = decimal("time_series_return")
        comparison_peer_count = cast(int, _input(inputs, "comparison_peer_count", int))
        cross = (
            optional_decimal("cross_sectional_percentile")
            if comparison_peer_count >= 5
            else None
        )
        sector = optional_decimal("sector_relative_return")
        momentum_complete = cross is not None and sector is not None
        bullish_alignment = sum(
            (
                time_series_return > 0,
                cross is not None and cross >= bullish_cross_min,
                sector is not None and sector > 0,
            )
        )
        bearish_alignment = sum(
            (
                time_series_return < 0,
                cross is not None and cross <= bearish_cross_max,
                sector is not None and sector < 0,
            )
        )
        alignment_count = (
            bullish_alignment
            if direction == "BULLISH"
            else bearish_alignment
            if direction == "BEARISH"
            else 0
        )

        liquidity_acceptable = False
        if structure is not None:
            liquidity_acceptable = all(
                leg.contract.bid is not None
                and leg.contract.ask is not None
                and leg.contract.mark is not None
                and leg.contract.mark > 0
                and (leg.contract.ask - leg.contract.bid) / leg.contract.mark
                <= maximum_spread
                and leg.contract.open_interest is not None
                and leg.contract.open_interest >= minimum_oi
                and leg.contract.volume is not None
                and leg.contract.volume >= minimum_volume
                for leg in structure.legs
            )
        mid_debit: Decimal | None = None
        conservative_debit: Decimal | None = None
        if structure is not None:
            if all(leg.contract.mark is not None for leg in structure.legs):
                mid_debit = sum(
                    (
                        cast(Decimal, leg.contract.mark)
                        * (Decimal(1) if leg.position is OptionLegPosition.LONG else Decimal(-1))
                        for leg in structure.legs
                    ),
                    Decimal(0),
                )
            if all(
                (
                    leg.contract.ask
                    if leg.position is OptionLegPosition.LONG
                    else leg.contract.bid
                )
                is not None
                for leg in structure.legs
            ):
                conservative_debit = sum(
                    (
                        cast(
                            Decimal,
                            leg.contract.ask
                            if leg.position is OptionLegPosition.LONG
                            else leg.contract.bid,
                        )
                        * (Decimal(1) if leg.position is OptionLegPosition.LONG else Decimal(-1))
                        for leg in structure.legs
                    ),
                    Decimal(0),
                )

        if bullish_core is False and bearish_core is False:
            verdict = "FAIL"
        elif direction == "CONFLICTING":
            verdict = "WATCH"
        elif direction in {"BULLISH", "BEARISH"}:
            verdict = (
                "PASS"
                if liquidity_acceptable
                and momentum_complete
                and alignment_count >= required_alignment
                else "FAIL"
                if not liquidity_acceptable
                else "WATCH"
            )
        else:
            # Missing or mixed-negative core evidence cannot support a
            # directional signal. UNKNOWN remains visible in the gate outputs,
            # but it is never positive evidence for WATCH.
            verdict = "FAIL"

        return ComponentValues(
            (
                ("bearish_core_gate", TypedValue(OPTIONAL_BOOLEAN, bearish_core)),
                ("bullish_core_gate", TypedValue(OPTIONAL_BOOLEAN, bullish_core)),
                ("direction", TypedValue(SKEW_DIRECTION, direction)),
                (
                    "conservative_debit",
                    TypedValue(OPTIONAL_DECIMAL, conservative_debit),
                ),
                ("liquidity_acceptable", TypedValue(B, liquidity_acceptable)),
                ("momentum_alignment_count", TypedValue(INTEGER, alignment_count)),
                ("momentum_complete", TypedValue(B, momentum_complete)),
                ("mid_debit", TypedValue(OPTIONAL_DECIMAL, mid_debit)),
                (
                    "normalized_call_skew",
                    TypedValue(D, decimal("normalized_call_skew")),
                ),
                (
                    "normalized_put_skew",
                    TypedValue(D, decimal("normalized_put_skew")),
                ),
                ("call_skew_zscore", TypedValue(OPTIONAL_DECIMAL, call_zscore)),
                ("put_skew_zscore", TypedValue(OPTIONAL_DECIMAL, put_zscore)),
                (
                    "historical_valid_observations",
                    TypedValue(INTEGER, historical_valid_observations),
                ),
                (
                    "call_atm_iv_minus_rv",
                    TypedValue(D, decimal("call_atm_iv_minus_rv")),
                ),
                (
                    "put_atm_iv_minus_rv",
                    TypedValue(D, decimal("put_atm_iv_minus_rv")),
                ),
                (
                    "call_wing_iv_minus_rv",
                    TypedValue(D, decimal("call_wing_iv_minus_rv")),
                ),
                (
                    "put_wing_iv_minus_rv",
                    TypedValue(D, decimal("put_wing_iv_minus_rv")),
                ),
                (
                    "call_wing_iv_minus_atm_iv",
                    TypedValue(D, decimal("call_wing_iv_minus_atm_iv")),
                ),
                (
                    "put_wing_iv_minus_atm_iv",
                    TypedValue(D, decimal("put_wing_iv_minus_atm_iv")),
                ),
                ("time_series_return", TypedValue(D, time_series_return)),
                ("cross_sectional_percentile", TypedValue(OPTIONAL_DECIMAL, cross)),
                ("comparison_peer_count", TypedValue(INTEGER, comparison_peer_count)),
                ("sector_relative_return", TypedValue(OPTIONAL_DECIMAL, sector)),
                ("score", TypedValue(D, Decimal(alignment_count))),
                ("structure", TypedValue(OPTIONAL_OPTION_STRUCTURE, structure)),
                ("verdict", TypedValue(VERDICT, verdict)),
            )
        )


class DoubleCalendarStructure(BaseComponent):
    """Compose one put calendar and one call calendar without a new domain type."""

    __slots__ = ()
    definition = _definition(
        "asa.stonk.options",
        "double_calendar_structure",
        ComponentCategory.TRANSFORM,
        (
            PortDefinition("chain", OPTION_CHAIN),
            PortDefinition("front_expiration", DATE),
            PortDefinition("back_expiration", DATE),
        ),
        (PortDefinition("structures", OPTION_STRUCTURE_LIST),),
        (
            ParameterDefinition("put_delta_target", D),
            ParameterDefinition("call_delta_target", D),
        ),
        version="1.0.1",
        algorithm_version="1.0.1",
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        chain = cast(OptionChain, _input(inputs, "chain", OptionChain))
        front = cast(date, _input(inputs, "front_expiration", date))
        back = cast(date, _input(inputs, "back_expiration", date))
        put_target = cast(Decimal, _parameter(parameters, "put_delta_target", Decimal))
        call_target = cast(Decimal, _parameter(parameters, "call_delta_target", Decimal))
        put_front = _nearest_common_strike_delta(
            chain, front, back, OptionType.PUT, put_target
        )
        call_front = _nearest_common_strike_delta(
            chain, front, back, OptionType.CALL, call_target
        )
        if put_front is None or call_front is None:
            return ComponentValues(
                (("structures", TypedValue(OPTION_STRUCTURE_LIST, ())),)
            )
        structures = (
            _calendar(chain, front, back, OptionType.PUT, put_front.strike, "put"),
            _calendar(chain, front, back, OptionType.CALL, call_front.strike, "call"),
        )
        return ComponentValues((("structures", TypedValue(OPTION_STRUCTURE_LIST, structures)),))


class OptionStructureCollectionLiquidity(BaseComponent):
    """Require coherent quoted liquidity fields on every selected leg."""

    __slots__ = ()
    definition = _definition(
        "asa.stonk.options",
        "option_structure_collection_liquidity",
        ComponentCategory.PREDICATE,
        (PortDefinition("structures", OPTION_STRUCTURE_LIST),),
        (PortDefinition("acceptable", B),),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        structures = cast(tuple[OptionStructure, ...], inputs.get("structures").value)
        contracts = tuple(leg.contract for structure in structures for leg in structure.legs)
        acceptable = bool(contracts) and all(
            contract.bid is not None
            and contract.ask is not None
            and contract.mark is not None
            and contract.open_interest is not None
            and contract.volume is not None
            and contract.bid >= 0
            and contract.ask >= contract.bid
            and contract.mark > 0
            and contract.open_interest >= 0
            and contract.volume >= 0
            for contract in contracts
        )
        return ComponentValues((("acceptable", TypedValue(B, acceptable)),))


class EarningsCalendarLiquidity(BaseComponent):
    """Hard quote/OI gate plus conservative coarse volume supplement."""

    __slots__ = ()
    definition = _definition(
        "asa.stonk.options",
        "earnings_calendar_liquidity",
        ComponentCategory.PREDICATE,
        (PortDefinition("structure", OPTION_STRUCTURE),),
        (
            PortDefinition("acceptable", B),
            PortDefinition("volume_band", VOLUME_BAND),
            PortDefinition("volume_supplement_strong", B),
            PortDefinition("volume_downgrade_reason", VOLUME_DOWNGRADE_REASON),
        ),
        (ParameterDefinition("minimum_volume_band", VOLUME_BAND),),
        version="1.1.0",
        algorithm_version="1.1.0",
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        structure = cast(OptionStructure, _input(inputs, "structure", OptionStructure))
        minimum_band = cast(str, _parameter(parameters, "minimum_volume_band", str))
        band_rank = {"UNKNOWN": 0, "LOW": 1, "ADEQUATE": 2, "HIGH": 3}
        if minimum_band not in band_rank:
            raise ComponentContractError("earnings calendar liquidity policy is invalid")
        contracts = tuple(leg.contract for leg in structure.legs)
        acceptable = bool(contracts) and all(
            contract.bid is not None
            and contract.ask is not None
            and contract.mark is not None
            and contract.bid >= 0
            and contract.ask >= contract.bid
            and contract.mark > 0
            and contract.open_interest is not None
            and contract.open_interest > 0
            for contract in contracts
        )
        volumes = tuple(contract.volume for contract in contracts)
        raw_band = (
            0
            if any(volume is None for volume in volumes)
            else compute_option_volume_band(min(cast(int, volume) for volume in volumes))
        )
        volume_band = (
            "UNKNOWN"
            if raw_band == 0
            else "LOW"
            if raw_band == 1
            else "ADEQUATE"
            if raw_band == 2
            else "HIGH"
        )
        supplement_strong = band_rank[volume_band] >= band_rank[minimum_band]
        downgrade_reason = (
            "NONE"
            if supplement_strong
            else "UNKNOWN_VOLUME"
            if volume_band == "UNKNOWN"
            else "BELOW_MINIMUM_VOLUME_BAND"
        )
        return ComponentValues(
            (
                ("acceptable", TypedValue(B, acceptable)),
                ("volume_band", TypedValue(VOLUME_BAND, volume_band)),
                ("volume_supplement_strong", TypedValue(B, supplement_strong)),
                ("volume_downgrade_reason", TypedValue(VOLUME_DOWNGRADE_REASON, downgrade_reason)),
            )
        )


class OptionStructureDebit(BaseComponent):
    """Calculate explicit mark and conservative debits from observed leg values."""

    __slots__ = ()
    definition = _definition(
        "asa.stonk.options",
        "option_structure_debit",
        ComponentCategory.TRANSFORM,
        (PortDefinition("structure", OPTION_STRUCTURE),),
        (
            PortDefinition("mid_debit", OPTIONAL_DECIMAL),
            PortDefinition("conservative_debit", OPTIONAL_DECIMAL),
        ),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        structure = cast(OptionStructure, _input(inputs, "structure", OptionStructure))
        marks = tuple(item.contract.mark for item in structure.legs)
        mid: Decimal | None = None
        if all(value is not None for value in marks):
            mid = sum(
                (
                    cast(Decimal, item.contract.mark)
                    * item.quantity
                    * (Decimal(1) if item.position is OptionLegPosition.LONG else Decimal(-1))
                    for item in structure.legs
                ),
                Decimal(0),
            )
        conservative_values = tuple(
            item.contract.ask if item.position is OptionLegPosition.LONG else item.contract.bid
            for item in structure.legs
        )
        conservative: Decimal | None = None
        if all(value is not None for value in conservative_values):
            conservative = sum(
                (
                    cast(Decimal, value)
                    * item.quantity
                    * (Decimal(1) if item.position is OptionLegPosition.LONG else Decimal(-1))
                    for item, value in zip(structure.legs, conservative_values, strict=True)
                ),
                Decimal(0),
            )
        return ComponentValues(
            (
                ("conservative_debit", TypedValue(OPTIONAL_DECIMAL, conservative)),
                ("mid_debit", TypedValue(OPTIONAL_DECIMAL, mid)),
            )
        )


SHARED_STONK_COMPONENTS: tuple[BaseComponent, ...] = (
    RequiredEvidenceGate(),
    SecurityUniverseFilter(),
    DeterministicSecurityCap(),
    WeightedScoreWithCeiling(),
    TwoFactorWeightedScore(),
    VerdictClassifier(),
    VerdictEligibilityGate(),
    VerdictEligibilitySupplementGate(),
)

OPTIONS_STONK_COMPONENTS: tuple[BaseComponent, ...] = (
    EarningsEventWindow(),
    EarningsEventProjection(),
    ForwardFactorEligibilityGate(),
    ExpirationPairSelector(),
    DtePairSelector(),
    ExpirationPairProjection(),
    ExpirationGapProjection(),
    ForwardFactor(),
    ImpliedForwardVolatility(),
    OptionLegLiquidity(),
    DeltaNearestLeg(),
    CalendarStructure(),
    NearestCommonStrikeCalendar(),
    VerticalStructure(),
    SkewMomentumResearchDecision(),
    DoubleCalendarStructure(),
    OptionStructureCollectionLiquidity(),
    EarningsCalendarLiquidity(),
    OptionStructureDebit(),
)
