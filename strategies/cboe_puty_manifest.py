"""Frozen Cboe PUTY production manifest."""

from dataclasses import replace

from strategies.cboe_put_manifest import CBOE_PUT_MANIFEST
from strategies.manifest import ManifestMetadata, ParameterSpec

STRATEGY_ID = "index_putwrite_cboe_puty"
STRATEGY_VERSION = "1.0.0"

CBOE_PUTY_MANIFEST = replace(
    CBOE_PUT_MANIFEST,
    strategy_id=STRATEGY_ID,
    strategy_version=STRATEGY_VERSION,
    metadata=ManifestMetadata(
        "Cboe S&P 500 2% OTM PutWrite",
        "Monthly cash-secured standard SPX put writing below 98% of the reference.",
        ("index", "options", "putwrite", "otm"),
    ),
    parameters=tuple(
        ParameterSpec("strike_fraction", "Decimal", "0.98") if item.name == "strike_rule" else item
        for item in CBOE_PUT_MANIFEST.parameters
    )
    + (ParameterSpec("strike_comparator", "String", "lt"),),
)
