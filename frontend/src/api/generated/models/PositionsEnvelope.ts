/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { FreshnessResponse } from './FreshnessResponse';
import type { PositionsDataResponse } from './PositionsDataResponse';
import type { RunResponse } from './RunResponse';
export type PositionsEnvelope = {
    run: RunResponse;
    freshness: FreshnessResponse;
    data: PositionsDataResponse;
};
