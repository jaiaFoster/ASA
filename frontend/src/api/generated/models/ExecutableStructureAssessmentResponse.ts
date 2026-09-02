/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ExactOptionLegResponse } from './ExactOptionLegResponse';
import type { ModeledEntryResponse } from './ModeledEntryResponse';
import type { SelectionDiagnosticResponse } from './SelectionDiagnosticResponse';
export type ExecutableStructureAssessmentResponse = {
    assessment_identity: string;
    originating_result_identity: string;
    subject: string;
    intended_structure_kind: string;
    status: string;
    available_structure_kind: (string | null);
    exact_legs: Array<ExactOptionLegResponse>;
    selection_diagnostics: Array<SelectionDiagnosticResponse>;
    modeled_entry: (ModeledEntryResponse | null);
    evidence_snapshot_identity: string;
    assessed_at: string;
    reason_code: (string | null);
};
