"""A skeletal blackboard system.

The library supplies the board, the shared structure through which
independent agents contribute to one result. The public surface is the set
of names in ``__all__``; every other name is internal.
"""

from blackboard._board import (
    BlackboardError,
    Board,
    BoardChange,
    Conflict,
    Contribution,
    DuplicateRegionError,
    Level,
    RegionKindError,
    Register,
    RegisterState,
    UndeclaredRegionError,
    UnsetRegisterError,
    Written,
)

__all__ = [
    "BlackboardError",
    "Board",
    "BoardChange",
    "Conflict",
    "Contribution",
    "DuplicateRegionError",
    "Level",
    "RegionKindError",
    "Register",
    "RegisterState",
    "UndeclaredRegionError",
    "UnsetRegisterError",
    "Written",
]
