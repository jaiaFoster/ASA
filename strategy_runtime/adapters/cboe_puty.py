"""Provider-blind Cboe PUTY production contract."""

from dataclasses import replace

from strategies.cboe_puty_manifest import STRATEGY_ID, STRATEGY_VERSION
from strategy_runtime.adapters.cboe_put import CBOE_PUT_CONTRACT

CBOE_PUTY_CONTRACT = replace(
    CBOE_PUT_CONTRACT,
    strategy_id=STRATEGY_ID,
    version=STRATEGY_VERSION,
    description="Cboe monthly cash-secured 2% OTM standard SPX PutWrite methodology.",
)
