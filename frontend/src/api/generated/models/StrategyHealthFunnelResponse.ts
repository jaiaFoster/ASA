/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ReasonCountResponse } from './ReasonCountResponse';
export type StrategyHealthFunnelResponse = {
    strategy_id: string;
    active_subjects: number;
    evaluated: number;
    missing_data: number;
    no_signal: number;
    retained_nonactive: number;
    evidence_sufficient: number;
    structure_eligible_or_constructible: number;
    gates_passed: number;
    watch: number;
    passed: number;
    typed_unknown_counts: Array<ReasonCountResponse>;
    typed_rejection_counts: Array<ReasonCountResponse>;
};
