/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ModeledPnLPointResponse } from './ModeledPnLPointResponse';
export type ModeledPnLSurfaceResponse = {
    surface_identity: string;
    structure_assessment_identity: string;
    valuation_model_and_version: string;
    valuation_time: string;
    spot_reference: string;
    points: Array<ModeledPnLPointResponse>;
    entry_fill_assumption: string;
    volatility_assumptions: Record<string, string>;
    annual_risk_free_rate: string;
    annual_dividend_yield: string;
    contract_multiplier: string;
    semantics?: string;
};
