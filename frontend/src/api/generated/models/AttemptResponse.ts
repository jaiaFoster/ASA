/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type AttemptResponse = {
    screening_cycle_id: string;
    pair_evaluation_id: string;
    sequence: number;
    capability: string;
    provider_id: string;
    priority: number;
    fulfillment_status: string;
    outcome: string;
    diagnostic_code: (string | null);
    retryable: boolean;
    safe_summary: (string | null);
    recorded_at: string;
};
