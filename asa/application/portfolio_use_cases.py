import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TypeVar
from uuid import UUID, uuid4

from asa.application.ports.brokers import (
    BrokerAccountsResult,
    BrokerPortfolioProvider,
    BrokerPositionsResult,
)
from asa.application.ports.runs import RunPublicationRepository
from asa.contracts.market import FreshnessStatus
from asa.contracts.portfolio import (
    BrokerAccount,
    EquityPosition,
    OptionPositionLeg,
    OptionType,
    PortfolioSnapshot,
    PositionSide,
    PublishedPortfolio,
    validate_snapshot,
)
from asa.contracts.runs import PublicationRecord, RunRecord, RunStatus, RunStepName

Clock = Callable[[], datetime]
T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class RunPortfolioResult:
    run_id: UUID
    status: RunStatus
    publication_id: UUID | None


@dataclass(frozen=True, slots=True)
class PublishedPortfolioView:
    publication: PublishedPortfolio
    run: RunRecord
    latest_run: RunRecord
    freshness_status: FreshnessStatus
    serving_last_success: bool
    account_count: int
    equity_position_count: int
    option_leg_count: int


class RunPortfolioIntelligence:
    def __init__(
        self,
        provider: BrokerPortfolioProvider,
        repository: RunPublicationRepository,
        clock: Clock = lambda: datetime.now(UTC),
    ) -> None:
        self._provider = provider
        self._repository = repository
        self._clock = clock
        self._logger = logging.getLogger("asa.portfolio_run")

    def execute(
        self,
        requested_at: datetime,
        release_sha: str,
        effective_config_hash: str,
    ) -> RunPortfolioResult:
        run = self._repository.create_run(
            requested_at.astimezone(UTC), release_sha, effective_config_hash
        )
        current_step = RunStepName.ACQUIRE_PORTFOLIO
        provider_name = self._provider.name
        self._repository.start_run(run.id, self._clock())
        try:
            accounts, positions = self._acquire(run.id)
            provider_name = accounts.provider
            current_step = RunStepName.NORMALIZE_PORTFOLIO
            snapshot = self._run_step(
                run.id,
                current_step,
                provider_name,
                lambda: self._normalize(accounts, positions),
            )
            current_step = RunStepName.VALIDATE_PUBLICATION
            self._run_step(
                run.id,
                current_step,
                provider_name,
                lambda: validate_snapshot(snapshot),
            )
            current_step = RunStepName.PUBLISH
            publication = self._repository.publish_portfolio(run.id, snapshot, self._clock())
            self._log_step(run.id, current_step, snapshot.provider, None)
            return RunPortfolioResult(run.id, RunStatus.SUCCEEDED, publication.id)
        except Exception as exc:
            detail = str(exc)[:500] or exc.__class__.__name__
            self._repository.fail_run(
                run.id,
                current_step,
                self._clock(),
                "portfolio_run_failed",
                detail,
            )
            self._log_step(run.id, current_step, provider_name, None)
            return RunPortfolioResult(run.id, RunStatus.FAILED, None)

    def _acquire(self, run_id: UUID) -> tuple[BrokerAccountsResult, BrokerPositionsResult]:
        step = RunStepName.ACQUIRE_PORTFOLIO
        self._repository.start_step(run_id, step, self._clock())
        accounts = self._provider.fetch_accounts()
        positions = self._provider.fetch_positions()
        if accounts.provider != positions.provider:
            raise ValueError("broker account and position providers must match")
        self._repository.complete_step(run_id, step, self._clock())
        account_id = accounts.accounts[0].external_account_id if accounts.accounts else None
        self._log_step(run_id, step, accounts.provider, account_id)
        return accounts, positions

    def _run_step(
        self,
        run_id: UUID,
        step: RunStepName,
        provider: str,
        operation: Callable[[], T],
    ) -> T:
        self._repository.start_step(run_id, step, self._clock())
        result = operation()
        self._repository.complete_step(run_id, step, self._clock())
        self._log_step(run_id, step, provider, None)
        return result

    @staticmethod
    def _normalize(
        accounts_result: BrokerAccountsResult,
        positions_result: BrokerPositionsResult,
    ) -> PortfolioSnapshot:
        accounts = tuple(
            BrokerAccount(
                id=uuid4(),
                connection_id=item.connection_id,
                external_account_id=item.external_account_id.strip(),
                provider=item.provider,
                account_type=item.account_type.strip().lower(),
                display_name=item.display_name.strip(),
                currency=item.currency.strip().upper(),
                observed_at=item.observed_at.astimezone(UTC),
            )
            for item in accounts_result.accounts
        )
        account_ids = {item.external_account_id: item.id for item in accounts}
        equities = tuple(
            EquityPosition(
                account_id=account_ids[item.external_account_id],
                symbol=item.symbol.strip().upper(),
                quantity=item.quantity,
                average_cost=item.average_cost,
                observed_at=item.observed_at.astimezone(UTC),
                original_provider=item.original_provider,
            )
            for item in positions_result.equities
        )
        option_legs = tuple(
            OptionPositionLeg(
                account_id=account_ids[item.external_account_id],
                underlying_symbol=item.underlying_symbol.strip().upper(),
                option_symbol=item.option_symbol.strip().upper(),
                option_type=OptionType(item.option_type.lower()),
                strike=item.strike,
                expiration=item.expiration,
                quantity=item.quantity,
                side=PositionSide(item.side.lower()),
                average_price=item.average_price,
                observed_at=item.observed_at.astimezone(UTC),
                original_provider=item.original_provider,
            )
            for item in positions_result.option_legs
        )
        evidence_observed_at = [account.observed_at for account in accounts]
        evidence_observed_at.extend(position.observed_at for position in equities)
        evidence_observed_at.extend(leg.observed_at for leg in option_legs)
        observed_at = min(evidence_observed_at)
        return PortfolioSnapshot(
            observed_at=observed_at,
            provider=accounts_result.provider,
            provider_request_id=(
                f"{accounts_result.provider_request_id}:{positions_result.provider_request_id}"
            ),
            accounts=accounts,
            equity_positions=equities,
            option_legs=option_legs,
        )

    def _log_step(
        self,
        run_id: UUID,
        step: RunStepName,
        provider: str,
        account_id: str | None,
    ) -> None:
        self._logger.info(
            "portfolio_run_step",
            extra={
                "run_id": str(run_id),
                "run_step": step.value,
                "provider": provider,
                "account_id": account_id,
            },
        )


class PublishedPortfolioQuery:
    def __init__(
        self,
        repository: RunPublicationRepository,
        fresh_for: timedelta,
        clock: Clock = lambda: datetime.now(UTC),
    ) -> None:
        self._repository = repository
        self._fresh_for = fresh_for
        self._clock = clock

    def current(self) -> PublishedPortfolioView | None:
        publication = self._repository.current_portfolio()
        if publication is None:
            return None
        run = self._repository.get_run(publication.run_id)
        latest_run = self._repository.latest_run()
        if run is None or latest_run is None:
            raise RuntimeError("published portfolio has incomplete run provenance")
        freshness = (
            FreshnessStatus.FRESH
            if publication.snapshot.observed_at >= self._clock() - self._fresh_for
            else FreshnessStatus.STALE
        )
        return PublishedPortfolioView(
            publication=publication,
            run=run,
            latest_run=latest_run,
            freshness_status=freshness,
            serving_last_success=(
                latest_run.id != run.id and latest_run.status is RunStatus.FAILED
            ),
            account_count=len(publication.snapshot.accounts),
            equity_position_count=len(publication.snapshot.equity_positions),
            option_leg_count=len(publication.snapshot.option_legs),
        )


class RunQueryService:
    def __init__(self, repository: RunPublicationRepository) -> None:
        self._repository = repository

    def get(self, run_id: UUID) -> RunRecord | None:
        return self._repository.get_run(run_id)

    def latest(self) -> RunRecord | None:
        return self._repository.latest_run()

    def publication_for(self, run_id: UUID) -> PublicationRecord | None:
        publication = self._repository.current_publication()
        return publication if publication is not None and publication.run_id == run_id else None
