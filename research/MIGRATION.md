# Research provenance migration

Date: 2026-09-25

This file records how pre-existing ASA research relates to the new canonical external strategy research library.

## Canonical distinction

- `research/` — external strategy evidence, literature synthesis, qualification, provenance, and ASA capability mapping.
- `project/research/` — ASA-specific empirical studies, preregistrations, data adequacy, operational observations, forward outcomes, and project research artifacts.

No historical directory is deleted or overwritten by this bootstrap.

## Existing material incorporated by reference

### TGSM

Historical artifacts:

- `project/research/TGSM-RESEARCH-001/preregistration-v1.json`
- `project/research/TGSM-RESEARCH-001/evidence-qualification-v1.json`
- `project/research/TGSM-RESEARCH-001/research-outcome-v1.json`
- `project/reports/TGSM-RESEARCH-001-RES-02.md`
- `project/reports/TGSM-RESEARCH-001-RES-06.md`
- `project/reports/ASA-RELIABILITY-RESEARCH-001.md`
- `docs/reference-strategies/S001-founder-research-definition.yaml`

New external-research entry:

- `research/strategies/ASA-RSCH-TGSM-001.md`

Migration interpretation: prior TGSM work is preserved as rigorous ASA-internal evidence about reproducibility, data requirements, and inability to run a qualified historical experiment. It is **not** relabeled as external evidence.

### SPY 30-DTE put credit spread

Historical artifacts:

- `project/reports/STRATEGY-LIBRARY-001-SL-02-SELECTION.md`
- `project/reports/STRATEGY-LIBRARY-001-CLOSURE.md`

New external-research entry:

- `research/strategies/ASA-RSCH-SPY-PCS-001.md`
- `research/sources/OA-SPY-PCS-2021.yaml`

Migration interpretation: the prior source-intake packet established that the public rules were explicit enough for faithful implementation. It did not establish research-grade external qualification. The inherited bibliographic record therefore carries a re-verification requirement.

### Skew Momentum

Historical artifact:

- `docs/contracts/skew-momentum-evidence.md`

New external-research entry:

- `research/strategies/ASA-RSCH-SKEW-MOMENTUM-001.md`

Migration interpretation: ASA's current policy and deterministic evidence contracts are preserved as internal specification context. No claim is made that the combined strategy has external empirical support until literature research establishes that.

## Future migration rule

When other legacy research is incorporated:

1. preserve the original artifact;
2. add a provenance link rather than copying claims without attribution;
3. classify inherited evidence as `ASA_PRIOR_INTERNAL` unless an external source is independently recovered;
4. record what remains unverified;
5. never upgrade implementation success, internal backtests, or synthetic fixtures into external research qualification.
