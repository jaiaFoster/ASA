/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { TradeProposalLegResponse } from './TradeProposalLegResponse';
import type { TradeQuantityResponse } from './TradeQuantityResponse';
export type OptionTradeProposalResponse = {
    status?: string;
    proposal_identity: string;
    originating_result_identity: string;
    underlying: string;
    strategy_id: string;
    strategy_version: string;
    structure: string;
    structure_assessment_identity: string;
    legs: Array<TradeProposalLegResponse>;
    modeled_net_debit_or_credit: string;
    entry_model_version: string;
    entry_calculated_at: string;
    liquidity: string;
    capital_required: TradeQuantityResponse;
    maximum_loss: TradeQuantityResponse;
    maximum_profit: TradeQuantityResponse;
    breakeven: TradeQuantityResponse;
    evidence_snapshot_identity: string;
    constructibility: string;
    assumptions: Array<string>;
    rationale: Array<string>;
    risk_notes: Array<string>;
    invalidation_notes: Array<string>;
};
