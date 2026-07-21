# Stonk legacy decommissioning

STONK-005 completes decommissioning at the ASA repository boundary. The legacy
Stonk application was inspected as read-only evidence at revision
`5f3fec846f70e9739cf3f15695fd587f0604344c`; it was never copied into ASA and is
not an ASA runtime dependency.

## Final disposition

| Legacy concern | ASA disposition |
|---|---|
| Strategy calculations | Extracted into pure, registered Components |
| Strategy assembly | Replaced by canonical Strategy Manifests |
| Ranking | Owned by the ASA Ranking Engine; legacy sorter not copied |
| Portfolio allocation | Owned by the ASA Portfolio Engine; legacy allocation not copied |
| Broker/provider access | Excluded from Strategy Core |
| Service orchestration and mutable state | Not migrated |
| Presentation rows | Not migrated |
| Disabled clone strategies | Not migrated |
| Compatibility runtime | Not required and not created |

The four manifest strategy IDs are the supported compatibility interface for
the migrated behavior. Compatibility means stable canonical strategy identity
and deterministic outputs—not retention of legacy Python modules, service
classes, provider payloads, or call signatures.

The external Stonk checkout can therefore be removed without affecting ASA
imports, tests, graph compilation, execution, or replay. Historical source
paths and the pinned revision remain only in migration documentation and test
provenance.

## Enforced boundary

Architecture regression coverage rejects imports from legacy application
namespaces, imports through a `legacy` namespace, and dynamic path injection in
the migrated strategy modules. ASA has one execution path: manifest → compiled
graph → registered Components → immutable result and trace.
