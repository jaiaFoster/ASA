from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from asa.application.portfolio_structures import project_option_structures
from asa.application.portfolio_use_cases import PublishedPortfolioView
from asa.application.portfolio_valuation import project_portfolio_valuation
from asa.contracts.market import MarketObservation
from asa.contracts.runs import PublicationRecord, RunRecord


class IngestQuotesRequest(BaseModel):
    symbols: set[str] = Field(min_length=1)


class ProvenanceResponse(BaseModel):
    selected_provider: str
    original_provider: str
    cache_status: str
    freshness_status: str
    fallback_reason: str | None
    provider_request_id: str


class QuoteResponse(BaseModel):
    symbol: str
    price: Decimal
    currency: str
    observed_at: datetime
    received_at: datetime
    provenance: ProvenanceResponse

    @classmethod
    def from_domain(cls, observation: MarketObservation) -> "QuoteResponse":
        provenance = observation.provenance
        return cls(
            symbol=observation.symbol,
            price=observation.price,
            currency=observation.currency,
            observed_at=observation.observed_at,
            received_at=observation.received_at,
            provenance=ProvenanceResponse(
                selected_provider=provenance.selected_provider,
                original_provider=provenance.original_provider,
                cache_status=provenance.cache_status.value,
                freshness_status=provenance.freshness_status.value,
                fallback_reason=provenance.fallback_reason,
                provider_request_id=provenance.provider_request_id,
            ),
        )


class IngestQuotesResponse(BaseModel):
    observations: list[QuoteResponse]


class HealthResponse(BaseModel):
    status: str


class BuildIdentityResponse(BaseModel):
    application_version: str
    api_version: str
    release_sha: str | None


class StartRunRequest(BaseModel):
    requested_at: datetime
    release_sha: str = Field(min_length=1, max_length=64)
    effective_config_hash: str = Field(min_length=1, max_length=128)


class RunStepResponse(BaseModel):
    name: str
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    failure_detail: str | None


class RunResponse(BaseModel):
    id: UUID
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    release_sha: str
    effective_config_hash: str
    failure_code: str | None
    failure_detail: str | None
    publication_id: UUID | None
    steps: list[RunStepResponse]

    @classmethod
    def from_domain(
        cls,
        run: RunRecord,
        publication: PublicationRecord | None,
    ) -> "RunResponse":
        return cls(
            id=run.id,
            status=run.status.value,
            started_at=run.started_at,
            completed_at=run.completed_at,
            release_sha=run.release_sha,
            effective_config_hash=run.effective_config_hash,
            failure_code=run.failure_code,
            failure_detail=run.failure_detail,
            publication_id=None if publication is None else publication.id,
            steps=[
                RunStepResponse(
                    name=step.name.value,
                    status=step.status.value,
                    started_at=step.started_at,
                    completed_at=step.completed_at,
                    failure_detail=step.failure_detail,
                )
                for step in run.steps
            ],
        )


class FreshnessResponse(BaseModel):
    as_of: datetime
    status: str
    serving_last_success: bool


class AccountResponse(BaseModel):
    id: UUID
    external_account_id: str
    provider: str
    account_type: str
    display_name: str
    currency: str
    cash_balance: Decimal | None
    cash_available_for_withdrawal: Decimal | None
    buying_power: Decimal | None
    account_value: Decimal | None
    observed_at: datetime


class EquityPositionResponse(BaseModel):
    account_id: UUID
    symbol: str
    quantity: Decimal
    average_cost: Decimal | None
    observed_at: datetime
    original_provider: str


class OptionLegResponse(BaseModel):
    account_id: UUID
    underlying_symbol: str
    option_symbol: str
    option_type: str
    strike: Decimal
    expiration: date
    quantity: Decimal
    side: str
    average_price: Decimal | None
    observed_at: datetime
    original_provider: str


class MonetaryValueResponse(BaseModel):
    amount: Decimal | None
    currency: str
    authority: str
    observed_at: datetime
    unknown_reason: str | None


class PositionValuationResponse(BaseModel):
    position_key: str
    market_value: MonetaryValueResponse
    profit_and_loss: MonetaryValueResponse


class OptionStructureResponse(BaseModel):
    kind: str
    option_symbols: list[str]


class UnmatchedOptionLegResponse(BaseModel):
    option_symbol: str
    reason: str


class PortfolioDataResponse(BaseModel):
    publication_id: UUID
    snapshot_id: UUID
    provider: str
    account_count: int
    equity_position_count: int
    option_leg_count: int
    accounts: list[AccountResponse]


class PositionsDataResponse(BaseModel):
    publication_id: UUID
    snapshot_id: UUID
    equity_positions: list[EquityPositionResponse]
    option_legs: list[OptionLegResponse]
    option_structures: list[OptionStructureResponse]
    unmatched_option_legs: list[UnmatchedOptionLegResponse]
    equity_valuations: list[PositionValuationResponse]
    option_leg_valuations: list[PositionValuationResponse]


class PortfolioEnvelope(BaseModel):
    run: RunResponse
    freshness: FreshnessResponse
    data: PortfolioDataResponse

    @classmethod
    def from_view(cls, view: PublishedPortfolioView) -> "PortfolioEnvelope":
        publication = view.publication
        snapshot = publication.snapshot
        return cls(
            run=RunResponse.from_domain(
                view.run,
                PublicationRecord(
                    publication.publication_id,
                    publication.run_id,
                    publication.snapshot_id,
                    publication.published_at,
                ),
            ),
            freshness=FreshnessResponse(
                as_of=snapshot.observed_at,
                status=view.freshness_status.value,
                serving_last_success=view.serving_last_success,
            ),
            data=PortfolioDataResponse(
                publication_id=publication.publication_id,
                snapshot_id=publication.snapshot_id,
                provider=snapshot.provider,
                account_count=view.account_count,
                equity_position_count=view.equity_position_count,
                option_leg_count=view.option_leg_count,
                accounts=[
                    AccountResponse.model_validate(account, from_attributes=True)
                    for account in snapshot.accounts
                ],
            ),
        )


class PositionsEnvelope(BaseModel):
    run: RunResponse
    freshness: FreshnessResponse
    data: PositionsDataResponse

    @classmethod
    def from_view(cls, view: PublishedPortfolioView) -> "PositionsEnvelope":
        publication = view.publication
        snapshot = publication.snapshot
        run_response = RunResponse.from_domain(
            view.run,
            PublicationRecord(
                publication.publication_id,
                publication.run_id,
                publication.snapshot_id,
                publication.published_at,
            ),
        )
        freshness = FreshnessResponse(
            as_of=snapshot.observed_at,
            status=view.freshness_status.value,
            serving_last_success=view.serving_last_success,
        )
        structures = project_option_structures(snapshot.option_legs)
        valuation = project_portfolio_valuation(snapshot)
        return cls(
            run=run_response,
            freshness=freshness,
            data=PositionsDataResponse(
                publication_id=publication.publication_id,
                snapshot_id=publication.snapshot_id,
                equity_positions=[
                    EquityPositionResponse.model_validate(item, from_attributes=True)
                    for item in snapshot.equity_positions
                ],
                option_legs=[
                    OptionLegResponse(
                        account_id=item.account_id,
                        underlying_symbol=item.underlying_symbol,
                        option_symbol=item.option_symbol,
                        option_type=item.option_type.value,
                        strike=item.strike,
                        expiration=item.expiration,
                        quantity=item.quantity,
                        side=item.side.value,
                        average_price=item.average_price,
                        observed_at=item.observed_at,
                        original_provider=item.original_provider,
                    )
                    for item in snapshot.option_legs
                ],
                option_structures=[
                    OptionStructureResponse(
                        kind=item.kind.value,
                        option_symbols=[leg.option_symbol for leg in item.legs],
                    )
                    for item in structures.structures
                ],
                unmatched_option_legs=[
                    UnmatchedOptionLegResponse(
                        option_symbol=item.leg.option_symbol,
                        reason=item.reason.value,
                    )
                    for item in structures.unmatched_legs
                ],
                equity_valuations=[
                    PositionValuationResponse.model_validate(item, from_attributes=True)
                    for item in valuation.equity_positions
                ],
                option_leg_valuations=[
                    PositionValuationResponse.model_validate(item, from_attributes=True)
                    for item in valuation.option_legs
                ],
            ),
        )
