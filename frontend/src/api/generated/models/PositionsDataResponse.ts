/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { EquityPositionResponse } from './EquityPositionResponse';
import type { OptionLegResponse } from './OptionLegResponse';
export type PositionsDataResponse = {
    publication_id: string;
    snapshot_id: string;
    equity_positions: Array<EquityPositionResponse>;
    option_legs: Array<OptionLegResponse>;
};
