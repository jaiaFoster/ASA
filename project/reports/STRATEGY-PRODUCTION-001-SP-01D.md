# STRATEGY-PRODUCTION-001 — SP-01D

Primary ticket: `SP-01D` — X07 index dividends and security-master facts.

## Outcome

The provider-neutral market-data contract now owns two distinct canonical
capabilities:

- `INDEX_DIVIDEND_POINTS_V1` carries published, effective-dated index-level
  dividend points for an INDEX instrument.
- `SECURITY_MASTER_V1` carries point-in-time security type and positive shares
  outstanding for an EQUITY instrument.

Both values participate in deterministic market-observation identity,
serialization, provenance, freshness, resolution, sealed snapshots, and replay.
No provider falsely declares either capability, so absence remains typed
unavailability until an authoritative provider is integrated.

## Boundary proof

Constituent corporate actions cannot satisfy `INDEX_DIVIDEND_POINTS_V1`; an
index dividend observation must carry the dedicated index-level value. Security
classification is canonical data, not a strategy-private ticker table. The
contracts retain their effective date independently from ASA acquisition and
recording times.

## Verification

- X07/security-master contract, invariant, identity, provenance, and replay tests: green.
- Full repository suite on the merged SP-02B base: `3841 passed, 50 skipped`.
- Static, architecture, and Lean validation are recorded on the PR.
