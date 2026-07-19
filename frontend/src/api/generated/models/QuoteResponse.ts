/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ProvenanceResponse } from './ProvenanceResponse';
export type QuoteResponse = {
    symbol: string;
    price: number | string;
    currency: string;
    observed_at: string;
    received_at: string;
    provenance: ProvenanceResponse;
};
