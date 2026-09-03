/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ScreeningResultResponse } from './ScreeningResultResponse';
export type ScreeningResultsEnvelope = {
    results: Array<ScreeningResultResponse>;
    total: number;
    limit: number;
    offset: number;
    snapshot_identity: string;
    scope: ScreeningResultsEnvelope.scope;
    retained_nonactive_total: number;
};
export namespace ScreeningResultsEnvelope {
    export enum scope {
        ALL_LATEST = 'all_latest',
        ACTIVE_UNIVERSE = 'active_universe',
    }
}
