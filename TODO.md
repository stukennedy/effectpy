# EffectPy Roadmap / TODOs

This document tracks planned work to reach near-parity with Effect TS (core + streams + schedules + supervision) in Python. Items marked [x] are implemented in the codebase.

## Core Effect
- [x] `map`/`flat_map`/`catch_all`/`provide` (baseline)
- [x] `zip` (sequential)
- [x] `zipWith` (sequential)
- [x] `fold` (handle success and failure)
- [x] `foldEffect`/`matchEffect`
- [x] `ensuring` (finalizer always runs)
- [x] `acquire_release` (bracket)
- [x] `on_error`/`on_interrupt`
- [x] `timeout` (return Optional)
- [x] `either`/`mapError`/`refineOrDie`
- [x] `uninterruptible`/`uninterruptibleMask` (baseline)

## Concurrency
- [x] `zip_par` (parallel zip with cancellation on failure)
- [x] `race` (first-completer; cancels other)
- [x] `for_each_par` with bounded parallelism
- [x] `raceFirst`/`raceAll`/`mergeAll`
- [x] Interrupt propagation semantics across combinators (cancel pending on failures)

## Schedules & Retry/Repeat
- [x] `Schedule` abstraction (recurs, spaced, exponential, jittered)
- [x] `retry` with `Schedule`
- [x] `repeat` with `Schedule`

## Resources & Scope
- [x] `Layer` + `Scope` (baseline)
 - [x] Effect-level `scoped` helpers (build/use/teardown in a scope)
 - [x] Richer layer memoization and error composition (safe teardown on partial failures; parallel acquisition cleanup)

## Primitives
- [x] `Deferred` (one-shot completion + await)
- [x] `Ref` (atomic)
- [x] `FiberRef` (fiber-local state)
- [x] `Queue` (shutdown, backpressure signals)
- [x] `Hub` (pub/sub broadcast)

## Streams / Channels
- [x] Basic `Stream` with stages (no error channel yet), termination via queue close, run_collect
- [x] Core combinators: `map`, `merge`, `buffer`; sinks: `run_fold`
- [x] `Sink` type and error channel semantics (`StreamE` + `Sink` + `sink_fold`)
 - [x] Resource-scoped stages and termination protocol (via `via_acquire_release`, `run_scoped`)
- [x] More combinators: `timeout`, `throttle`, `filter`, `take`, `mapEffect` (via `via_effect`)
 - [x] Replace/extend `Pipeline` with `Stream` primitives (uses `StreamE.from_channel`)

## Runtime & Fibers
- [x] `Runtime` + `Fiber` (asyncio) and AnyIO variant
- [x] Fiber id/status, `join`, `inheritRefs`
- [x] `Supervisor` hooks (start/end/failure)

## Services & Environment
- [x] `Context` (type-indexed DI)
 - [x] Service tags/helpers: `provide_service`, `service` accessors

## Time & Random
- [x] `Clock` service and helpers (`sleep`)
- [x] `TestClock` for deterministic tests
- [x] `Random`/`TestRandom`

## Observability
- [x] Basic logger/metrics/tracer + instrumentation
 - [x] Structured logger fields, levels and filtering, JSON output, correlation ids
 - [x] Metrics counters/gauges via registry with labels
 - [x] Tracing attributes/events/links; improved OTLP-ish encoding

## Data & Errors
- [x] Data types: `Option`, `Either`, `Duration`
- [x] Error modeling helpers & `Cause` integration across combinators (Effect.annotate -> Cause annotations)

## Testing & Tooling
- [ ] Test kit: in-memory `Supervisor` utilities/helpers
- [ ] Property-based/integration tests for concurrency and streams

---

Recently completed in this session:

- [x] Core: `zip`, `zipWith`, `fold`, `foldEffect`, `ensuring`, `acquire_release`, `timeout`, `mapError`, `refineOrDie`, `on_error`, `on_interrupt`.
- [x] Concurrency: `zip_par`, `race`, `for_each_par`, `raceFirst`, `raceAll`, `mergeAll` with proper cancellation.
- [x] Schedule + combinators: `Schedule` (recurs/spaced/exponential/jittered), `retry`, `repeat`.
- [x] Primitives: `Deferred`, `Ref`, `FiberRef`, `Queue`, `Hub`.
- [x] Streams: base `Stream`, error-channel `StreamE`, sinks (`sink_fold`, `sink_head`, `sink_drain`), combinators (`map`, `filter`, `take`, `buffer`, `merge`, `timeout`, `throttle`), resource-scoped stages, and Pipeline integration.
- [x] Runtime & Fibers: Fiber ids/status/join, `Supervisor` hooks.
- [x] Services: `Clock`/`TestClock` (with `sleep`/`current_time`), `Random`/`TestRandom` (with helpers).
- [x] Tests added and passing for all above.
