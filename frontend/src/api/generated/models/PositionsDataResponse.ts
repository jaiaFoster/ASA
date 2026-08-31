/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { EquityPositionResponse } from './EquityPositionResponse';
import type { OptionLegResponse } from './OptionLegResponse';
import type { OptionStructureResponse } from './OptionStructureResponse';
import type { PositionValuationResponse } from './PositionValuationResponse';
import type { UnmatchedOptionLegResponse } from './UnmatchedOptionLegResponse';
export type PositionsDataResponse = {
    publication_id: string;
    snapshot_id: string;
    equity_positions: Array<EquityPositionResponse>;
    option_legs: Array<OptionLegResponse>;
    option_structures: Array<OptionStructureResponse>;
    unmatched_option_legs: Array<UnmatchedOptionLegResponse>;
    equity_valuations: Array<PositionValuationResponse>;
    option_leg_valuations: Array<PositionValuationResponse>;
};
