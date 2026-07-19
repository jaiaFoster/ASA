/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { HealthResponse } from '../models/HealthResponse';
import type { IngestQuotesRequest } from '../models/IngestQuotesRequest';
import type { IngestQuotesResponse } from '../models/IngestQuotesResponse';
import type { PortfolioEnvelope } from '../models/PortfolioEnvelope';
import type { PositionsEnvelope } from '../models/PositionsEnvelope';
import type { QuoteResponse } from '../models/QuoteResponse';
import type { RunResponse } from '../models/RunResponse';
import type { StartRunRequest } from '../models/StartRunRequest';
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
}
