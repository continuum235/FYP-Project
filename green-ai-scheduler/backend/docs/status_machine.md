## Status machine

| Transition | Trigger |
|------------|---------|
| `QUEUED` (initial) | `POST /jobs` |
| `QUEUED` → `WAITING` | Tick + policy `WAIT` on start-candidate |
| `WAITING`/`QUEUED`/`PAUSED` → `RUNNING` | Tick + policy `RUN` + worker slot free |
| `RUNNING` → `PAUSED` | Tick + policy `WAIT`/`PAUSE` on running job (system) |
| `*` → `MANUALLY_PAUSED` | `POST /jobs/{id}/pause` |
| `MANUALLY_PAUSED` → `QUEUED` | `POST /jobs/{id}/resume` only |
| `RUNNING` → `COMPLETED` | Training finishes all epochs |

## Deadline proximity (GreedyPolicy)

```
time_remaining = deadline - now
remaining_epochs = total_epochs - current_epoch
estimated_remaining_hours = (remaining_epochs / total_epochs) * max(time_running + time_waiting, 0.05h)
RUN-forcing when time_remaining <= estimated_remaining_hours + safety_margin_hours
```
