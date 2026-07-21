"""Pure shared Components extracted from the pinned legacy Stonk strategies.

The implementations consume ASA domain contracts only.  They contain no
provider access, legacy payload handling, portfolio policy, ranking authority,
runtime dispatch, clock access, persistence, or presentation behavior.
"""

from __future__ import annotations

import hashlib
from datetime import date
from decimal import Context, Decimal, ROUND_HALF_EVEN, localcontext
from typing import cast

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
FINANCIAL_DECIMAL_CONTEXT = Context(prec=34, rounding=ROUND_HALF_EVEN)


def _definition(
    namespace: str,
    name: str,
    category: ComponentCategory,
    inputs: tuple[PortDefinition, ...],
    outputs: tuple[PortDefinition, ...],
    parameters: tuple[ParameterDefinition, ...] = (),
) -> ComponentDefinition:
    return ComponentDefinition(
        namespace,
        name,
        "1.0.0",
        category,
        inputs,
        outputs,
        parameters,
        algorithm_version="1.0.0",
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
        (PortDefinition("selected", EXPIRATION_COLLECTION),),
        (
            ParameterDefinition("front_min_dte", INTEGER),
            ParameterDefinition("front_max_dte", INTEGER),
            ParameterDefinition("back_min_dte", INTEGER),
            ParameterDefinition("back_max_dte", INTEGER),
        ),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        expirations = cast(
            ExpirationCollection, _input(inputs, "expirations", ExpirationCollection)
        )
        event = cast(EarningsEvent, _input(inputs, "event", EarningsEvent))
        bounds = {
            name: cast(int, _parameter(parameters, name, int))
            for name in ("front_min_dte", "front_max_dte", "back_min_dte", "back_max_dte")
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
        )
        selected = min(
            pairs,
            key=lambda pair: (
                (event.earnings_date - pair[0].expiration_date).days
                + (pair[1].expiration_date - event.earnings_date).days,
                pair[0].expiration_date,
                pair[1].expiration_date,
            ),
            default=None,
        )
        result = ExpirationCollection(expirations.as_of, selected or ())
        return ComponentValues((("selected", TypedValue(EXPIRATION_COLLECTION, result)),))


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


class ForwardFactor(BaseComponent):
    """Compute source-qualified front IV divided by forward IV minus one."""

    __slots__ = ()
    definition = _definition(
        "asa.stonk.options",
        "forward_factor",
        ComponentCategory.SCORE,
        (
            PortDefinition("front_ex_earnings_iv", D),
            PortDefinition("implied_forward_iv", D),
        ),
        (PortDefinition("factor", D),),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        front = cast(Decimal, _input(inputs, "front_ex_earnings_iv", Decimal))
        forward = cast(Decimal, _input(inputs, "implied_forward_iv", Decimal))
        if front < 0 or forward <= 0:
            raise ComponentContractError(
                "forward factor requires non-negative front IV and positive forward IV"
            )
        return ComponentValues((("factor", TypedValue(D, front / forward - Decimal(1))),))


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
        if front_dte < 1 or back_dte <= front_dte:
            raise ComponentContractError("back DTE must be greater than positive front DTE")
        with localcontext(FINANCIAL_DECIMAL_CONTEXT):
            numerator = back_iv * back_iv * back_dte - front_iv * front_iv * front_dte
            variance = numerator / Decimal(back_dte - front_dte)
            if variance <= 0:
                raise ComponentContractError("implied forward variance must be positive")
            forward_iv = variance.sqrt()
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
        long_contract = _nearest_delta(chain.contracts, expiration, option_type, long_target)
        short_contract = _nearest_delta(
            chain.contracts,
            expiration,
            option_type,
            short_target,
            excluded=frozenset({long_contract.identity}),
        )
        structure = OptionStructure(
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
        return ComponentValues((("structure", TypedValue(OPTION_STRUCTURE, structure)),))


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
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        chain = cast(OptionChain, _input(inputs, "chain", OptionChain))
        front = cast(date, _input(inputs, "front_expiration", date))
        back = cast(date, _input(inputs, "back_expiration", date))
        put_target = cast(Decimal, _parameter(parameters, "put_delta_target", Decimal))
        call_target = cast(Decimal, _parameter(parameters, "call_delta_target", Decimal))
        put_front = _nearest_delta(chain.contracts, front, OptionType.PUT, put_target)
        call_front = _nearest_delta(chain.contracts, front, OptionType.CALL, call_target)
        structures = (
            _calendar(chain, front, back, OptionType.PUT, put_front.strike, "put"),
            _calendar(chain, front, back, OptionType.CALL, call_front.strike, "call"),
        )
        return ComponentValues((("structures", TypedValue(OPTION_STRUCTURE_LIST, structures)),))


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
    VerdictClassifier(),
)

OPTIONS_STONK_COMPONENTS: tuple[BaseComponent, ...] = (
    EarningsEventWindow(),
    ExpirationPairSelector(),
    DtePairSelector(),
    ExpirationPairProjection(),
    ForwardFactor(),
    ImpliedForwardVolatility(),
    OptionLegLiquidity(),
    DeltaNearestLeg(),
    CalendarStructure(),
    NearestCommonStrikeCalendar(),
    VerticalStructure(),
    DoubleCalendarStructure(),
    OptionStructureDebit(),
)
