/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Extends, not duplicates, ScreeningResultResponse -- a refresh result
 * is a screening result plus how many live provider requests it took
 * (API-004's own "request_accounting" requirement). Never the raw
 * RequestAccountingEntry records themselves: provider identity, quota
 * detail, and retry mechanics stay internal
 * (architecture_principles: "provider_implementations_remain_completely_
 * internal"), not exposed in a public response.
 */
export type RefreshResultResponse = {
    updated_at: string;
    age_seconds: number;
    signal_id: string;
    signal_version: string;
    symbol: string;
    outcome: string;
    evaluation_state: string;
    verdict: (string | null);
    explanation: (string | null);
    metrics: Record<string, string>;
    observation_id?: (string | null);
    opportunity_id?: (string | null);
    opportunity_history_url?: (string | null);
    row_type?: (string | null);
    lifecycle_stage?: (string | null);
    status?: (string | null);
    data_quality?: (string | null);
    freshness?: (string | null);
    economics?: Record<string, string>;
    metric_types?: Record<string, string>;
    economics_types?: Record<string, string>;
    blockers?: Array<string>;
    warnings?: Array<string>;
    provenance?: Array<string>;
    canonical_facts?: Record<string, string>;
    named_derived_facts?: Record<string, string>;
    formula_versions?: Record<string, string>;
    gate_results?: Record<string, string>;
    direction?: (string | null);
    structure?: (string | null);
    reason_codes?: Array<string>;
    assumptions?: Array<string>;
    subject_snapshot_at: string;
    observed_at: string;
    received_at: string;
    evaluated_at: string;
    persisted_at: string;
    market_session_date?: (string | null);
    market_session_status?: string;
    last_refresh_attempt_at: string;
    last_successful_refresh_at: string;
    next_refresh_at?: (string | null);
    data_advanced_on_last_refresh?: boolean;
    freshness_status?: string;
    usability_status?: string;
    usability_reason?: string;
    warning_codes?: Array<string>;
    acquisition_started_at: string;
    acquisition_completed_at: string;
    input_time_skew_seconds?: number;
    request_count: number;
    provider_contacted: boolean;
    result_changed: boolean;
    refresh_failed: boolean;
};
