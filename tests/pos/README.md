# POS Test Suite

## Overview

Tests for the ASA2 POS repository bootstrap state. These tests verify structural and mechanical correctness only.

## Running Tests

```bash
python -m pip install -r tools/pos/requirements.txt
python -m pytest tests/pos -v
```

## What Is Tested

1. Required directories exist
2. Governance manifest parses correctly
3. Frozen governance file hashes match the manifest
4. Bootstrap status file parses
5. Role registry parses
6. All six POS schemas parse
7. Validator passes on the committed repository state
8. Validator fails when a frozen file hash is intentionally wrong (fixture test — does not touch real frozen files)
9. Generator output is deterministic
10. Generated files contain the required generated-file warning

## What Is NOT Tested Here

- Business logic or governance semantics
- POS record lifecycle (deferred to POS-BOOTSTRAP-02)
- Schema validation of actual records (no records exist yet at bootstrap)

## Safety

No test modifies any real frozen governance file. Hash-mismatch tests operate on temporary copies isolated to `tmp_path` fixtures.
