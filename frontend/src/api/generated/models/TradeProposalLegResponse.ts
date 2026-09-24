/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type TradeProposalLegResponse = {
    canonical_contract_identity: string;
    role: string;
    buy_or_sell: string;
    call_or_put: string;
    strike: string;
    expiration: string;
    quantity: string;
    bid: (string | null);
    ask: (string | null);
    midpoint: (string | null);
    actual_delta: (string | null);
    target_delta: (string | null);
    quote_observed_at: string;
};
