# blackboardx

A group of agents works on one problem. Each writes what it finds into a single shared record, every agent can read all of it, and no agent calls another; the record is the only channel between them. The blackboard literature calls a system skeletal when it supplies this structure with no domain knowledge inside, so that an application system is built on it by adding knowledge and control. `blackboardx` is skeletal in that sense. It supplies the board, and the control component's write path and notification dispatch; an application adds its agents, the content they write, and its rules.

The distribution name is `blackboardx`; the import name is `blackboard`.

## Install

```
pip install blackboardx
```

## The board

The board stores contributions in named regions under one total order, and it never reads what it stores. A region has one of two kinds. A level accumulates contributions in arrival order, and nothing stored is altered. A register holds one current value for a premise of the case; a write replaces the whole value under the version the writer read, and fails with the register's current version when another writer moved it first. One counter orders every write across all regions, so a contribution in one region stands in a definite order against a write in any other.

## Public API

Every public name is exported from `blackboard`; every other module is internal.

| Name | Holds |
| --- | --- |
| `Board` | The board: `declare`, `append`, `set`, `read_level`, `read_register`, `read_board` |
| `Level`, `Register` | The two region declarations |
| `Written`, `Conflict` | A register write the board sequenced, and one that named a stale version |
| `Contribution` | One unit read back from a level |
| `RegisterState` | A register's current value and version |
| `BoardChange` | One write to any region, as `read_board` returns it |
| `BlackboardError` | The base of every error the library raises |
| `UndeclaredRegionError` | An operation named a region that no declaration created |
| `DuplicateRegionError` | A declaration named a region that already exists |
| `RegionKindError` | An operation that takes a level named a register, or the reverse |
| `UnsetRegisterError` | A register was read before any write gave it a value |
| `BoardReader` | The three read operations, as the admission rule receives them |
| `ProposedContribution`, `ProposedRegisterWrite`, `ProposedWrite` | A write as the admission rule sees it, before sequencing |
| `Accept`, `Reject` | The admission rule's two verdicts |
| `AdmissionRule` | The type of the rule the application supplies |
| `Accepted`, `Rejected` | A write the control component admitted, and one it refused |
| `RejectionCause` | The closed set of causes for a refused write |
| `WriteAccepted`, `WriteRejected`, `AuditEvent` | The audit's records of writes that reached the board and writes that did not |
| `Agent` | An agent declaration: name, acknowledgment deadline, wake cap, and the delivery callback |
| `Notification`, `NotificationId` | One wake, and the identifier an acknowledgment names |
| `NotificationDispatched`, `NotificationAcknowledged`, `DeadlineExtended`, `PresumedFailed`, `WakeCapReached` | The audit's records of dispatch, acknowledgment, extension, presumed failure, and a reached wake cap |
| `DuplicateAgentError` | A registration named an agent that is already registered |
| `UnknownNotificationError` | The named notification was never issued to the acknowledging agent |
| `Clock`, `ScheduledCall` | The protocol for reading time and arming calls, and an armed call's handle |
| `SystemClock` | The default clock, the library's only reader of the operating system clock |
| `ManualClock` | The deterministic clock a test advances by hand |

## Example

```python
from blackboard import Board, Conflict, Level, Register, Written

board = Board([Level("application"), Register("window")])

# The register holds a premise: the time range under investigation.
board.set("window", ("2026-08-16T20:00", "2026-08-16T22:00"), expected_version=0)

# A level accumulates contributions; each write returns its sequence number.
sequence = board.append("application", {"observation": "error rate rose tenfold"})
assert sequence == 2

# A register write states the version it read. The first writer wins.
state = board.read_register("window")
widened = board.set(
    "window", ("2026-08-16T19:00", "2026-08-16T22:00"), expected_version=state.version
)
assert isinstance(widened, Written)

# A second writer holding the same version fails and learns the current one.
late = board.set(
    "window", ("2026-08-16T18:00", "2026-08-16T22:00"), expected_version=state.version
)
assert late == Conflict(current_version=widened.version)

# The whole record reads back in sequence order.
for change in board.read_board():
    print(change.sequence, change.region, change.content)
```

## License

Apache-2.0. The license text is in [LICENSE](LICENSE).
