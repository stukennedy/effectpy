# Retry & Schedules

Use `Schedule` to control retries and repeats.

```python
eff.retry(Schedule.recurs(3))
eff.retry(Schedule.exponential(0.1).jittered())
eff.repeat(Schedule.spaced(0.5))
```

See `effectpy.schedule` for available schedules.

