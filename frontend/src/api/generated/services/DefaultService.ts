/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { QuoteResponse } from '../models/QuoteResponse';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class DefaultService {
    /**
     * @param symbol
     * @returns QuoteResponse Latest canonical observation
     * @throws ApiError
     */
    public static getLatestQuote(
        symbol: string,
    ): CancelablePromise<QuoteResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/market/quotes/{symbol}',
            path: {
                'symbol': symbol,
            },
            errors: {
                404: `Unavailable`,
            },
        });
    }
}
