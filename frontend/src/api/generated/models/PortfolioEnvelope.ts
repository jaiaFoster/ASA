/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { FreshnessResponse } from './FreshnessResponse';
import type { PortfolioDataResponse } from './PortfolioDataResponse';
import type { RunResponse } from './RunResponse';
export type PortfolioEnvelope = {
    run: RunResponse;
    freshness: FreshnessResponse;
    data: PortfolioDataResponse;
};
