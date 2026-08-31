/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { OpportunityObservationResponse } from './OpportunityObservationResponse';
export type OpportunityHistoryResponse = {
    opportunity_id: string;
    observations: Array<OpportunityObservationResponse>;
    total: number;
    limit: number;
    offset: number;
};
