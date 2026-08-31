/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type TrackedCandidateResponse = {
    id: string;
    originating_observation_id: string;
    opportunity_id: (string | null);
    strategy_id: string;
    strategy_version: string;
    symbol: string;
    tracked_at: string;
    originating_observed_at: string;
    evidence_observed_at: string;
    exact_option_symbols: Array<string>;
};
