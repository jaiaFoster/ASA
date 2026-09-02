/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ExecutableStructureAssessmentResponse } from './ExecutableStructureAssessmentResponse';
import type { ModeledPnLSurfaceResponse } from './ModeledPnLSurfaceResponse';
import type { ScreeningResultResponse } from './ScreeningResultResponse';
/**
 * Additive composition; the signal and assessment remain independent.
 */
export type ScreeningExecutionReadinessResponse = {
    signal: ScreeningResultResponse;
    execution_assessment: ExecutableStructureAssessmentResponse;
    modeled_pnl?: (ModeledPnLSurfaceResponse | null);
};
