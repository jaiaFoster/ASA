/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { RunStepResponse } from './RunStepResponse';
export type RunResponse = {
    id: string;
    status: string;
    started_at: (string | null);
    completed_at: (string | null);
    release_sha: string;
    effective_config_hash: string;
    failure_code: (string | null);
    failure_detail: (string | null);
    publication_id: (string | null);
    steps: Array<RunStepResponse>;
};
