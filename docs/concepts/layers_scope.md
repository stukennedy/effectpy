# Layers & Scope

`Layer` acquires services into a `Context`, and `Scope` guarantees LIFO teardown.

- Compose sequentially with `+`, in parallel with `|`
- Build with `build`, `build_scoped` and `provide`/`provide_scoped`

```python
env = await (LoggerLayer | MetricsLayer | TracerLayer).build_scoped(Context(), Scope())
```

