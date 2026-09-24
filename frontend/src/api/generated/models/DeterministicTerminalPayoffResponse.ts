/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { PayoffQuantityResponse } from './PayoffQuantityResponse';
import type { TerminalPayoffPointResponse } from './TerminalPayoffPointResponse';
export type DeterministicTerminalPayoffResponse = {
    payoff_identity: string;
    structure_assessment_identity: string;
    model_version: string;
    expiration: string;
    points: Array<TerminalPayoffPointResponse>;
    contract_multiplier: string;
    entry_fill_assumption: string;
    maximum_loss: PayoffQuantityResponse;
    maximum_profit: PayoffQuantityResponse;
    breakevens: Array<string>;
    semantics: string;
};
