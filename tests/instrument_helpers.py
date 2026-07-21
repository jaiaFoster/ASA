"""Canonical Instrument fixtures shared by pipeline contract tests."""

from domain.operational import CanonicalInstrumentIdentity, Instrument, InstrumentKind

TEST_INSTRUMENT = Instrument(
    identity=CanonicalInstrumentIdentity("figi", "BBG000B9XRY4"),
    kind=InstrumentKind.EQUITY,
    display_symbol="AAPL",
    currency="USD",
)
