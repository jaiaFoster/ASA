from datetime import UTC, date, datetime
from decimal import Decimal

from domain import (
    CanonicalInstrumentIdentity,
    EvidenceKind,
    EvidenceReference,
    Instrument,
    InstrumentKind,
    OptionChain,
    OptionContract,
    OptionType,
    Security,
    SecurityAssetType,
)
from strategy_runtime.adapters.forward_factor_subject_first import _contract_at

OBSERVED_AT = datetime(2026, 8, 17, 19, 0, tzinfo=UTC)
EXPIRATION = date(2026, 9, 18)
EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "uni-03-regression"),)


def _security() -> Security:
    return Security(
        Instrument(
            CanonicalInstrumentIdentity("figi", "figi-SPGI"),
            InstrumentKind.EQUITY,
            "SPGI",
            "USD",
        ),
        "SPGI",
        SecurityAssetType.EQUITY,
        "XNYS",
    )


def _contract(contract_id: str, implied_volatility: str) -> OptionContract:
    return OptionContract(
        CanonicalInstrumentIdentity("asa-option-v1", contract_id),
        _security(),
        EXPIRATION,
        Decimal("550"),
        OptionType.CALL,
        Decimal("9"),
        Decimal("11"),
        Decimal("10"),
        10,
        100,
        Decimal("0.5"),
        None,
        None,
        None,
        None,
        Decimal(implied_volatility),
        OBSERVED_AT,
        EVIDENCE,
    )


def test_contract_selection_accepts_multiple_canonical_identities_deterministically() -> None:
    later = _contract("SPGI-adjusted", "0.31")
    canonical_first = _contract("SPGI-standard", "0.29")
    chain = OptionChain(
        "spgi-chain",
        _security(),
        OBSERVED_AT,
        (canonical_first, later),
        EVIDENCE,
    )

    selected = _contract_at(chain, EXPIRATION, Decimal("550"))

    assert selected is chain.contracts[0]
