"""Deterministic Provider documentation generation (MD-017)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from domain import MarketCapability
from domain.values import DomainInvariantError
from market_data.alpha_vantage import ALPHA_VANTAGE_CAPABILITIES
from market_data.finnhub import FINNHUB_CAPABILITIES
from market_data.fixture import FIXTURE_CAPABILITIES
from market_data.tradier import TRADIER_CAPABILITIES


@dataclass(frozen=True, slots=True)
class ProviderDocumentationSpec:
    provider_id: str
    capabilities: tuple[MarketCapability, ...]
    credential_names: tuple[str, ...]
    environments: tuple[str, ...]
    rate_limits: tuple[str, ...]
    known_limitations: tuple[str, ...]
    fixture_coverage: tuple[MarketCapability, ...]

    def __post_init__(self) -> None:
        if not self.provider_id or self.provider_id != self.provider_id.strip():
            raise DomainInvariantError("Provider documentation identity must be normalized")
        if not self.capabilities or set(self.fixture_coverage) != set(self.capabilities):
            raise DomainInvariantError("Provider documentation fixture coverage is incomplete")


PROVIDER_DOCUMENTATION = (
    ProviderDocumentationSpec(
        "deterministic_fixture",
        FIXTURE_CAPABILITIES,
        (),
        ("offline",),
        ("network requests: 0 (fixture)",),
        ("Deterministic test data only; never represents live market conditions.",),
        FIXTURE_CAPABILITIES,
    ),
    ProviderDocumentationSpec(
        "tradier",
        TRADIER_CAPABILITIES,
        ("ASA_TRADIER_ACCESS_TOKEN", "ASA_TRADIER_ENV"),
        ("sandbox", "production"),
        (
            "market data: 60 requests/minute (documented sandbox)",
            "market data: 120 requests/minute (documented production)",
        ),
        (
            "Option-chain quality is explicit when fields are absent.",
            "Validation requires an active account and applicable market-data entitlement.",
        ),
        TRADIER_CAPABILITIES,
    ),
    ProviderDocumentationSpec(
        "finnhub",
        FINNHUB_CAPABILITIES,
        ("ASA_FINNHUB_API_KEY",),
        ("production",),
        ("global calls: 30/second (documented)",),
        (
            "Daily candles use resolution D and UTC epoch request bounds.",
            "HTTP 200 with no_data is a normalized no_data failure.",
            "HTTP 200 with empty arrays is a normalized empty_payload failure.",
            "Candle availability may depend on subscription entitlement.",
        ),
        FINNHUB_CAPABILITIES,
    ),
    ProviderDocumentationSpec(
        "alpha_vantage",
        ALPHA_VANTAGE_CAPABILITIES,
        ("ASA_ALPHA_VANTAGE_API_KEY",),
        ("production",),
        ("unknown limits remain finite through configured request budgets",),
        (
            "Daily validation uses compact raw-as-traded output.",
            "Provider Note and Information payloads are diagnostics, not market data.",
        ),
        ALPHA_VANTAGE_CAPABILITIES,
    ),
)


def render_provider_page(spec: ProviderDocumentationSpec) -> str:
    capabilities = "\n".join(f"- `{item.value}`" for item in spec.capabilities)
    credentials = "\n".join(f"- `{item}`" for item in spec.credential_names) or "- None"
    environments = "\n".join(f"- `{item}`" for item in spec.environments)
    limits = "\n".join(f"- {item}" for item in spec.rate_limits)
    limitations = "\n".join(f"- {item}" for item in spec.known_limitations)
    coverage = "\n".join(f"- `{item.value}`" for item in spec.fixture_coverage)
    provider_argument = spec.provider_id
    return f"""<!-- GENERATED: run python -m market_data.documentation --write -->
# {spec.provider_id} Market Data Provider

## Capabilities

{capabilities}

## Configuration names

{credentials}

## Environments

{environments}

## Rate limits

{limits}

Configured runtime and validation budgets remain authoritative safety ceilings.

## Bounded validation

Dry run:

```text
python -m market_data.validation --provider {provider_argument}
```

Explicit opt-in execution:

```text
python -m market_data.validation --provider {provider_argument} --execute
```

## Known limitations

{limitations}

## Fixture coverage

{coverage}

Last live validation: not recorded in generated source; consult secret-free validation artifacts.
"""


def render_capability_matrix(specs: tuple[ProviderDocumentationSpec, ...]) -> str:
    capabilities = tuple(
        sorted({item for spec in specs for item in spec.capabilities}, key=lambda item: item.value)
    )
    header = "| Capability | " + " | ".join(spec.provider_id for spec in specs) + " |"
    divider = "|---|" + "---|" * len(specs)
    rows = [
        "| `"
        + capability.value
        + "` | "
        + " | ".join("yes" if capability in spec.capabilities else "—" for spec in specs)
        + " |"
        for capability in capabilities
    ]
    return "\n".join(
        (
            "<!-- GENERATED: run python -m market_data.documentation --write -->",
            "# Market Data Provider Capability Matrix",
            "",
            header,
            divider,
            *rows,
            "",
        )
    )


def generated_documents() -> dict[str, str]:
    pages = {
        f"docs/providers/{spec.provider_id}.md": render_provider_page(spec)
        for spec in PROVIDER_DOCUMENTATION
    }
    pages["docs/providers/CAPABILITY_MATRIX.md"] = render_capability_matrix(PROVIDER_DOCUMENTATION)
    return pages


def write_generated_documents(root: Path) -> None:
    for relative, content in generated_documents().items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def documentation_drift(root: Path) -> tuple[str, ...]:
    return tuple(
        relative
        for relative, expected in sorted(generated_documents().items())
        if not (root / relative).exists()
        or (root / relative).read_text(encoding="utf-8") != expected
    )


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Generate deterministic Provider documentation")
    parser.add_argument("--write", action="store_true")
    arguments = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if arguments.write:
        write_generated_documents(root)
        return 0
    drift = documentation_drift(root)
    if drift:
        print("Provider documentation drift: " + ", ".join(drift))
        return 1
    print("Provider documentation is current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
