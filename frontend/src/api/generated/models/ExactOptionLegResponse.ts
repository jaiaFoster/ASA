/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type ExactOptionLegResponse = {
    canonical_contract_identity: string;
    instrument_id_scheme: string;
    instrument_id_value: string;
    role: string;
    call_or_put: string;
    expiration: string;
    strike: string;
    long_or_short: string;
    quantity: string;
    bid: (string | null);
    ask: (string | null);
    midpoint: (string | null);
    actual_delta: (string | null);
    target_delta: (string | null);
    source_observed_at: string;
};
