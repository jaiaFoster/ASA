/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CapabilityCheckResponse } from './CapabilityCheckResponse';
export type ProviderResultResponse = {
    provider: string;
    configuration_status: string;
    checks: Array<CapabilityCheckResponse>;
};
