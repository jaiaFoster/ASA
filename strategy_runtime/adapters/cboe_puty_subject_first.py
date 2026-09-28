"""Cboe PUTY reuse binding over the shared PUT stack."""

from datetime import datetime
from decimal import Decimal
from functools import partial

from screening.subject_planning import SubjectPlanConsumer
from strategies.cboe_put_evaluation import PutwriteStrikePolicy
from strategies.cboe_put_planning import bootstrap_demands, expand_demands
from strategies.cboe_puty_manifest import CBOE_PUTY_MANIFEST
from strategy_runtime.adapters.cboe_put_subject_first import (
    _assessment,
    _prepare,
    build_cboe_putwrite_subject_first_adapter,
)
from strategy_runtime.adapters.cboe_puty import CBOE_PUTY_CONTRACT
from strategy_runtime.subject_preparation import SubjectPreparationBinding


def build_cboe_puty_subject_preparation_binding(now: datetime) -> SubjectPreparationBinding[object]:
    parameters = {item.name: item.value for item in CBOE_PUTY_MANIFEST.parameters}
    policy = PutwriteStrikePolicy(
        Decimal(str(parameters["strike_fraction"])),
        str(parameters["strike_comparator"]),
        "G_PUTY_STRIKE_EXISTS_UNKNOWN",
        "CBOE_PUTY_ALL_GATES_PASS",
    )
    return SubjectPreparationBinding(
        SubjectPlanConsumer(
            CBOE_PUTY_CONTRACT.strategy_id,
            bootstrap_demands(now),
            partial(expand_demands, now=now),
        ),
        partial(_prepare, now),
        partial(
            build_cboe_putwrite_subject_first_adapter,
            contract=CBOE_PUTY_CONTRACT,
            strike_policy=policy,
        ),
        build_execution_assessment=partial(_assessment, strike_policy=policy),
    )
