/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ProviderResultResponse } from './ProviderResultResponse';
export type ValidateResponse = {
    overall_status: string;
    dry_run: boolean;
    generated_at: string;
    providers: Array<ProviderResultResponse>;
};
