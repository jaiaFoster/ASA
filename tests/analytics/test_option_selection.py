from datetime import UTC, date, datetime
from decimal import Decimal

from analytics.option_selection import select_canonical_contract
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


def _contract(contract_id: str) -> OptionContract:
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
        Decimal("0.30"),
        OBSERVED_AT,
        EVIDENCE,
    )


def test_multiple_canonical_identities_select_by_chain_order() -> None:
    chain = OptionChain(
        "spgi-chain",
        _security(),
        OBSERVED_AT,
        (_contract("SPGI-standard"), _contract("SPGI-adjusted")),
        EVIDENCE,
    )

    selected = select_canonical_contract(chain, EXPIRATION, Decimal("550"), OptionType.CALL)

    assert selected is chain.contracts[0]
