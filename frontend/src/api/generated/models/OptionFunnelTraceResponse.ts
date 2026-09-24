/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CapabilityDemandDiagnosticResponse } from './CapabilityDemandDiagnosticResponse';
import type { GateOutcomeResponse } from './GateOutcomeResponse';
export type OptionFunnelTraceResponse = {
    strategy_id: string;
    symbol: string;
    candidate_inclusion_reason: string;
    declared_capabilities: Array<string>;
    acquisition: Array<CapabilityDemandDiagnosticResponse>;
    gate_outcomes: Array<GateOutcomeResponse>;
    signal_verdict: (string | null);
    evaluation_state: string;
    structure_status: (string | null);
    constructibility_reason: (string | null);
    terminal_state: string;
    terminal_reason: string;
};
