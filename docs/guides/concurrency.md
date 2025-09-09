# Concurrency

Parallel combinators:

- `zip_par(e1, e2)`
- `race(e1, e2)`; `race_first([...])`, `race_all([...])`
- `merge_all([...], parallelism=...)`
- `for_each_par(items, f, parallelism)`

All combinators cancel pending work on failure to ensure prompt interruption.

