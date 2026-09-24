/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { NamedValueResponse } from './NamedValueResponse';
/**
 * SP-01 stock/ETF proposal: strategy-emitted truth only, never sizing or returns.
 */
export type StockOpportunityProposalResponse = {
    originating_result_identity: string;
    instrument: string;
    strategy_id: string;
    strategy_version: string;
    strategy_description: string;
    status: StockOpportunityProposalResponse.status;
    action: (string | null);
    action_reason: (string | null);
    signal_verdict: (string | null);
    evaluation_state: string;
    evidence_observed_at: string;
    freshness: string;
    freshness_status: string;
    evidence_age_seconds: number;
    signal_metrics: Array<NamedValueResponse>;
    allocation: (string | null);
    allocation_reason: (string | null);
    unknown_reasons: Array<string>;
    rationale: Array<string>;
    invalidation_notes: Array<string>;
    warnings: Array<string>;
    provenance: Array<string>;
};
export namespace StockOpportunityProposalResponse {
    export enum status {
        ACTIONABLE = 'actionable',
        NO_ACTION = 'no_action',
        UNKNOWN = 'unknown',
    }
}
