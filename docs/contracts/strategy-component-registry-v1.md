# Strategy Component Registry v1

The Component Registry is an immutable exact-version catalog constructed from a finite tuple of
explicitly supplied `BaseComponent` instances. Construction completes before manifest compilation.

The registry:

- validates every component port and parameter type against one immutable Strategy Type System;
- rejects duplicate `(namespace, name, version)` identities;
- rejects capabilities outside the closed Core capability vocabulary;
- resolves only exact Component References;
- sorts registrations canonically;
- derives a pinned SHA-256 identity from the type-system identity and ordered Component identities;
- exposes no registration, removal, scanning, discovery, entry-point, import, or patch API.

Input order never affects registry contents or identity. Unknown names and compatible-looking,
range, or latest versions fail closed. The registry does not inspect the filesystem, installed
packages, environment, network, or manifest import strings.

Plugin Packages will later be explicitly supplied to this same construction boundary after Plugin
SDK validation. Plugins do not introduce a second registry or loading mechanism.
