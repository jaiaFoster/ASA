# TGSM-RUNTIME-001 — S001-02 evidence and universe

The existing effective-universe owner now supports immutable canonical
membership intervals and a source-pinned Select Sector SPDR membership. The
eleven members come from State Street's Select Sector listing; eligibility
begins at fund inception, so XLC and XLRE never appear before their real launch
and the original nine never appear before 1998-12-16.

`trailing_12m_total_return@1.0.0` is a generic registered derived calculation.
It uses thirteen completed UTC month-end observations and accepts only explicit
`split_and_dividend_adjusted` evidence. Split-only/raw observations and short
history fail closed. B002's existing SMA remains unchanged; S001 will supply it
the same total-return-capable evidence.

Sources:

- State Street Select Sector ETF list: https://www.ssga.com/us/en/individual/capabilities/equities/sector-investing/select-sector-etfs
- State Street XLC fund page (2018-06-18 inception)
- State Street XLRE fund page (2015-10-07 inception)
- State Street fund pages for the original nine (1998-12-16 inception)

No provider selection, strategy policy, runtime registration, or broker behavior
changes in this gate. Production availability remains fail-closed: the current
Alpha Vantage account's adjusted-history entitlement limitation is not bypassed.
