/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type CapabilityDemandDiagnosticResponse = {
    demand_id: string;
    capability: string;
    acquisition_result: string;
    evidence_usability: string;
    reused_across_consumers: boolean;
    attempt_count: number;
    missing_reason: (string | null);
};
