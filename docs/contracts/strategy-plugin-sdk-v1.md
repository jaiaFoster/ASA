# Strategy Plugin SDK v1

A plugin is immutable metadata plus a finite tuple of stateless Component instances. Plugins are
constructed explicitly by the application at process startup and combined into the ordinary
validated `ComponentRegistry`. The SDK performs no discovery, importing, entry-point scanning,
downloading, hot registration, runtime patching, or execution hooks.

Every contributed Component must use the plugin namespace and satisfy the same Component and Type
System contracts as Core components. Plugins extend vocabulary only; Core retains exclusive
ownership of graph validation, ordering, execution, tracing, replay, and lifecycle semantics.
