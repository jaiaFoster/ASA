/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type ScreeningOperationalHealthResponse = {
    last_attempted_batch_at: (string | null);
    last_successful_batch_at: (string | null);
    oldest_subject_age: (number | null);
    overdue_subject_count: number;
    last_batch_subject_count: number;
    last_batch_pair_count: number;
    last_batch_failure_count: number;
    last_batch_incomplete_diagnostic_count: number;
};
