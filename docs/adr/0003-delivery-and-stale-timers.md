# ADR 0003: Delivery failures and stale timer calls

Date: 2026-08-17

## Status

Accepted

## Context

ADR 0002 fixed callback delivery and the clock protocol but left three behaviors unstated, and implementing the notification increment surfaced them. A `threading.Timer` whose function has started ignores cancellation, so a cancelled deadline or batch-window call can still run. A delivery callback is application code and can raise. A callback that writes a zero-window register causes the next delivery during the current one, and doing that on the call stack bounds chained wakes by the interpreter's recursion limit rather than by any declared budget.

## Decision

**A stale timer call changes nothing.** Every armed deadline and batch window carries a generation, and the firing call presents the generation it was armed with; when the arming state has moved on, the call returns without effect. An extension therefore survives the replaced deadline firing after its cancellation, and a swept batch window cannot dispatch the next batch early. Rejected: trusting cancellation, which `threading.Timer` does not honor once the call has started.

**A raising callback is an undelivered wake, and the deadline machinery records it.** The exception is suppressed at the boundary, the remaining deliveries of the batch proceed, and the writer keeps its result. The raising agent never acknowledges, so its deadline passes and the audit records it presumed failed. Rejected: propagating the exception, which would abort deliveries already audited as dispatched and surface one agent's defect inside an unrelated writer's call.

**Deliveries drain from a queue, one flat loop per thread.** A callback that causes further dispatch enqueues the resulting deliveries and returns, so chained wakes cost queue entries, not stack frames, and deliveries leave in dispatch order. Rejected: delivering on the call stack, which crossed the interpreter's recursion limit near five hundred chained wakes.

## Consequences

- A wake cap, not the recursion limit, bounds a write-notify chain.
- An agent whose delivery raised is indistinguishable in the audit from one that received its wake and never acknowledged. Recording the exception itself is the application's concern, because the callback is the application's code.

## Alternatives rejected

Each decision above names its rejected alternative in place.
