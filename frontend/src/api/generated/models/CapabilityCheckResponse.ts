/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type CapabilityCheckResponse = {
    capability: string;
    normalized_check_status: string;
    diagnostic_detail_code: string;
    request_count: number;
    latency: (number | null);
    entitlement_status: string;
    schema_status: string;
    freshness_status: string;
    quota_metadata_when_safe: (Record<string, string> | null);
    redacted_failure_summary: (string | null);
};
