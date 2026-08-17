# ADR 0001: Project scope

Date: 2026-08-17

## Status

Accepted

## Context

A group of agents works on one problem. Each agent holds knowledge the others lack, none can produce the result alone, and no agent calls another; a shared record is the only channel between them. The blackboard architecture is the established answer to that arrangement. Some blackboard systems carry the knowledge of one problem inside them; a system that instead supplies only the working parts, to which an application adds knowledge and control, is what the literature calls skeletal.

The maintainer holds a specification of such a skeletal system, the shared solution model, and this library is its implementation. The specification fixes three layers. The board stores contributions in named regions under one total order and never reads what it stores. The control component determines who is notified of a change, whether a proposed write is admitted, whether budgets hold, and when a run ends. The application, which is not part of this library, supplies the agents, the content they write, and the rules the control component applies.

## Decision

The library implements the two lower layers and a creation surface, and nothing of any application.

- The board offers two region kinds. A level accumulates units in arrival order. A register holds one current value under a version number, and a write naming a stale version fails.
- The control component carries seven responsibilities: lifecycle, registry, dispatch, admission, completion, budget, and audit.
- A model is created from six things: region declarations, agent declarations, seed register values, an admission rule, a termination predicate, and run budgets.
- The import name is `blackboard`, one package in src layout. The public surface is the set of names in `blackboard.__all__`; every other name is internal.
- The distribution is published to PyPI as `pyblackboard`, publicly.
- Supported Python versions are 3.11 through 3.14, with `requires-python = ">=3.11"`; CI runs the suite on each of them.
- The license is Apache-2.0.

## Consequences

- No identifier in the library names any application's work; an application names its own model after its own problem.
- A capability the specification lacks is a specification change before it is code.
- The version-supported window moves as CPython versions enter and leave support, each move a reviewed change to `requires-python` and the CI matrix.

## Alternatives rejected

- The PyPI name `blackboard`: held since 2019 by an unrelated package.
- MIT: the project is corporate backed, and Apache-2.0 adds the patent grant that posture calls for.
- Supporting Python 3.10: it leaves upstream support in October 2026.
- A private distribution: the library carries no domain knowledge and nothing proprietary.
