/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { AttemptListResponse } from '../models/AttemptListResponse';
import type { AttemptSummaryResponse } from '../models/AttemptSummaryResponse';
import type { BuildIdentityResponse } from '../models/BuildIdentityResponse';
import type { CapabilitiesResponse } from '../models/CapabilitiesResponse';
import type { HealthResponse } from '../models/HealthResponse';
import type { IngestQuotesRequest } from '../models/IngestQuotesRequest';
import type { IngestQuotesResponse } from '../models/IngestQuotesResponse';
import type { OpportunityHistoryResponse } from '../models/OpportunityHistoryResponse';
import type { PortfolioEnvelope } from '../models/PortfolioEnvelope';
import type { PositionsEnvelope } from '../models/PositionsEnvelope';
import type { QuoteResponse } from '../models/QuoteResponse';
import type { RefreshResultResponse } from '../models/RefreshResultResponse';
import type { RunResponse } from '../models/RunResponse';
import type { ScreeningOperationalHealthResponse } from '../models/ScreeningOperationalHealthResponse';
import type { ScreeningResultResponse } from '../models/ScreeningResultResponse';
import type { ScreeningResultsEnvelope } from '../models/ScreeningResultsEnvelope';
import type { StartRunRequest } from '../models/StartRunRequest';
import type { StrategyHealthResponse } from '../models/StrategyHealthResponse';
import type { TrackCandidateRequest } from '../models/TrackCandidateRequest';
import type { TrackedCandidateDetailResponse } from '../models/TrackedCandidateDetailResponse';
import type { TrackedCandidateResponse } from '../models/TrackedCandidateResponse';
import type { ValidateRequest } from '../models/ValidateRequest';
import type { ValidateResponse } from '../models/ValidateResponse';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class DefaultService {
    /**
     * Health
     * @returns HealthResponse Successful Response
     * @throws ApiError
     */
    public static healthApiV1HealthGet(): CancelablePromise<HealthResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/health',
        });
    }
    /**
     * Version
     * @returns BuildIdentityResponse Successful Response
     * @throws ApiError
     */
    public static versionApiV1VersionGet(): CancelablePromise<BuildIdentityResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/version',
        });
    }
    /**
     * Readiness
     * @returns HealthResponse Successful Response
     * @throws ApiError
     */
    public static readinessApiV1ReadinessGet(): CancelablePromise<HealthResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/readiness',
        });
    }
    /**
     * Ingest Quotes
     * @param requestBody
     * @returns IngestQuotesResponse Successful Response
     * @throws ApiError
     */
    public static ingestQuotesApiV1MarketQuotesIngestPost(
        requestBody: IngestQuotesRequest,
    ): CancelablePromise<IngestQuotesResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/market/quotes/ingest',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Latest Quote
     * @param symbol
     * @returns QuoteResponse Successful Response
     * @throws ApiError
     */
    public static getLatestQuote(
        symbol: string,
    ): CancelablePromise<QuoteResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/market/quotes/{symbol}',
            path: {
                'symbol': symbol,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Start Run
     * @param requestBody
     * @returns RunResponse Successful Response
     * @throws ApiError
     */
    public static startRunApiV1RunsPost(
        requestBody: StartRunRequest,
    ): CancelablePromise<RunResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/runs',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Current Run
     * @returns RunResponse Successful Response
     * @throws ApiError
     */
    public static currentRunApiV1RunsCurrentGet(): CancelablePromise<RunResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/runs/current',
        });
    }
    /**
     * Get Run
     * @param runId
     * @returns RunResponse Successful Response
     * @throws ApiError
     */
    public static getRunApiV1RunsRunIdGet(
        runId: string,
    ): CancelablePromise<RunResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/runs/{run_id}',
            path: {
                'run_id': runId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Portfolio
     * @returns PortfolioEnvelope Successful Response
     * @throws ApiError
     */
    public static getPortfolio(): CancelablePromise<PortfolioEnvelope> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/portfolio',
        });
    }
    /**
     * Get Positions
     * @returns PositionsEnvelope Successful Response
     * @throws ApiError
     */
    public static getPositions(): CancelablePromise<PositionsEnvelope> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/positions',
        });
    }
    /**
     * Validate Market Data
     * @param requestBody
     * @returns ValidateResponse Successful Response
     * @throws ApiError
     */
    public static validateMarketDataOpsMarketDataValidatePost(
        requestBody: ValidateRequest,
    ): CancelablePromise<ValidateResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/ops/market-data/validate',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * List Attempts
     * @param screeningCycleId
     * @param pairEvaluationId
     * @param providerId
     * @param capability
     * @param outcome
     * @param recordedAfter
     * @param recordedBefore
     * @param limit
     * @param offset
     * @returns AttemptListResponse Successful Response
     * @throws ApiError
     */
    public static listAttemptsOpsScreeningAttemptsGet(
        screeningCycleId?: (string | null),
        pairEvaluationId?: (string | null),
        providerId?: (string | null),
        capability?: (string | null),
        outcome?: (string | null),
        recordedAfter?: (string | null),
        recordedBefore?: (string | null),
        limit: number = 100,
        offset?: number,
    ): CancelablePromise<AttemptListResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/ops/screening/attempts',
            query: {
                'screening_cycle_id': screeningCycleId,
                'pair_evaluation_id': pairEvaluationId,
                'provider_id': providerId,
                'capability': capability,
                'outcome': outcome,
                'recorded_after': recordedAfter,
                'recorded_before': recordedBefore,
                'limit': limit,
                'offset': offset,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Summarize Attempts
     * @param screeningCycleId
     * @param pairEvaluationId
     * @param providerId
     * @param capability
     * @param recordedAfter
     * @param recordedBefore
     * @returns AttemptSummaryResponse Successful Response
     * @throws ApiError
     */
    public static summarizeAttemptsOpsScreeningAttemptsSummaryGet(
        screeningCycleId?: (string | null),
        pairEvaluationId?: (string | null),
        providerId?: (string | null),
        capability?: (string | null),
        recordedAfter?: (string | null),
        recordedBefore?: (string | null),
    ): CancelablePromise<AttemptSummaryResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/ops/screening/attempts/summary',
            query: {
                'screening_cycle_id': screeningCycleId,
                'pair_evaluation_id': pairEvaluationId,
                'provider_id': providerId,
                'capability': capability,
                'recorded_after': recordedAfter,
                'recorded_before': recordedBefore,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Capabilities
     * @returns CapabilitiesResponse Successful Response
     * @throws ApiError
     */
    public static capabilitiesApiV1CapabilitiesGet(): CancelablePromise<CapabilitiesResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/capabilities',
        });
    }
    /**
     * Screening Operations
     * @returns ScreeningOperationalHealthResponse Successful Response
     * @throws ApiError
     */
    public static screeningOperationsApiV1ScreeningOperationsGet(): CancelablePromise<ScreeningOperationalHealthResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/screening/operations',
        });
    }
    /**
     * List Screening
     * @param limit
     * @param offset
     * @param signal
     * @param symbol
     * @param outcome
     * @param lifecycleStage
     * @param freshness
     * @param status
     * @param sortBy
     * @param sortOrder
     * @returns ScreeningResultsEnvelope Successful Response
     * @throws ApiError
     */
    public static listScreeningApiV1ScreeningGet(
        limit: number = 100,
        offset?: number,
        signal?: (string | null),
        symbol?: (string | null),
        outcome?: (string | null),
        lifecycleStage?: (string | null),
        freshness?: ('fresh' | 'stale' | null),
        status?: (string | null),
        sortBy?: (string | null),
        sortOrder: 'asc' | 'desc' = 'desc',
    ): CancelablePromise<ScreeningResultsEnvelope> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/screening',
            query: {
                'limit': limit,
                'offset': offset,
                'signal': signal,
                'symbol': symbol,
                'outcome': outcome,
                'lifecycle_stage': lifecycleStage,
                'freshness': freshness,
                'status': status,
                'sort_by': sortBy,
                'sort_order': sortOrder,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Strategy Health
     * @returns StrategyHealthResponse Successful Response
     * @throws ApiError
     */
    public static strategyHealthApiV1ScreeningHealthGet(): CancelablePromise<StrategyHealthResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/screening-health',
        });
    }
    /**
     * Opportunity History
     * @param opportunityId
     * @param limit
     * @param offset
     * @returns OpportunityHistoryResponse Successful Response
     * @throws ApiError
     */
    public static opportunityHistoryApiV1ScreeningOpportunitiesOpportunityIdHistoryGet(
        opportunityId: string,
        limit: number = 100,
        offset?: number,
    ): CancelablePromise<OpportunityHistoryResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/screening/opportunities/{opportunity_id}/history',
            path: {
                'opportunity_id': opportunityId,
            },
            query: {
                'limit': limit,
                'offset': offset,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * List Screening For Signal
     * @param signal
     * @param limit
     * @param offset
     * @param symbol
     * @param outcome
     * @param lifecycleStage
     * @param freshness
     * @param status
     * @param sortBy
     * @param sortOrder
     * @returns ScreeningResultsEnvelope Successful Response
     * @throws ApiError
     */
    public static listScreeningForSignalApiV1ScreeningSignalGet(
        signal: string,
        limit: number = 100,
        offset?: number,
        symbol?: (string | null),
        outcome?: (string | null),
        lifecycleStage?: (string | null),
        freshness?: ('fresh' | 'stale' | null),
        status?: (string | null),
        sortBy?: (string | null),
        sortOrder: 'asc' | 'desc' = 'desc',
    ): CancelablePromise<ScreeningResultsEnvelope> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/screening/{signal}',
            path: {
                'signal': signal,
            },
            query: {
                'limit': limit,
                'offset': offset,
                'symbol': symbol,
                'outcome': outcome,
                'lifecycle_stage': lifecycleStage,
                'freshness': freshness,
                'status': status,
                'sort_by': sortBy,
                'sort_order': sortOrder,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Screening Result
     * @param signal
     * @param symbol
     * @returns ScreeningResultResponse Successful Response
     * @throws ApiError
     */
    public static getScreeningResultApiV1ScreeningSignalSymbolGet(
        signal: string,
        symbol: string,
    ): CancelablePromise<ScreeningResultResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/screening/{signal}/{symbol}',
            path: {
                'signal': signal,
                'symbol': symbol,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Refresh Screening Result
     * @param signal
     * @param symbol
     * @returns RefreshResultResponse Successful Response
     * @throws ApiError
     */
    public static refreshScreeningResultApiV1ScreeningSignalSymbolRefreshPost(
        signal: string,
        symbol: string,
    ): CancelablePromise<RefreshResultResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/screening/{signal}/{symbol}/refresh',
            path: {
                'signal': signal,
                'symbol': symbol,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Tracked Candidates
     * @returns TrackedCandidateResponse Successful Response
     * @throws ApiError
     */
    public static getTrackedCandidates(): CancelablePromise<Array<TrackedCandidateResponse>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/portfolio/tracked-candidates',
        });
    }
    /**
     * Track Candidate
     * @param requestBody
     * @returns TrackedCandidateResponse Successful Response
     * @throws ApiError
     */
    public static trackCandidate(
        requestBody: TrackCandidateRequest,
    ): CancelablePromise<TrackedCandidateResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/portfolio/tracked-candidates',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Tracked Candidate
     * @param candidateId
     * @returns TrackedCandidateDetailResponse Successful Response
     * @throws ApiError
     */
    public static getTrackedCandidate(
        candidateId: string,
    ): CancelablePromise<TrackedCandidateDetailResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/portfolio/tracked-candidates/{candidate_id}',
            path: {
                'candidate_id': candidateId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
}
