/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { AssociationResponse } from './AssociationResponse';
import type { LifecycleObservationResponse } from './LifecycleObservationResponse';
import type { TrackedCandidateResponse } from './TrackedCandidateResponse';
export type TrackedCandidateDetailResponse = {
    candidate: TrackedCandidateResponse;
    lifecycle: Array<LifecycleObservationResponse>;
    associations: Array<AssociationResponse>;
    exit_policy_status: string;
};
