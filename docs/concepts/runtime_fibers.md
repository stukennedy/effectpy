# Runtime & Fibers

`Runtime` runs effects against a base `Context`, and `Fiber` represents a forked effect.

- `fork` returns a `Fiber` with `await_`, `join`, `interrupt`
- Supervisor hooks: start/end/failure
- AnyIO variant: `AnyIORuntime` (optional)

