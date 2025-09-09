# Effects

An `Effect[R, E, A]` describes an async computation that may fail with `E` and succeed with `A`. `R` is the environment type (services available in `Context`).

- Map/flat_map for composition
- Error channel via `Failure` and `catch_all`
- Resource safety with `acquire_release`, `ensuring`, `provide` / `provide_scoped`
- Timeouts, annotations, retry/repeat with `Schedule`

See the [core API](../reference/core.md) for all combinators.

