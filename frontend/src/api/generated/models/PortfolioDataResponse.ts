/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { AccountResponse } from './AccountResponse';
export type PortfolioDataResponse = {
    publication_id: string;
    snapshot_id: string;
    provider: string;
    account_count: number;
    equity_position_count: number;
    option_leg_count: number;
    accounts: Array<AccountResponse>;
};
