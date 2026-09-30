"""Wood for shelters: grove stock, carried units, and paid building work."""

WOOD = "wood"
GATHER_WOOD = "gather_wood"
GO_WOOD = "go_wood"
WAIT_WOOD = "wait_wood"
WOOD_STOCK = 12
WOOD_RENEWAL_EVERY = 40
WOOD_RENEWAL = 1
WOOD_PACK = 3
WORK_PER_WOOD = 4

# Shared wood yards (yard on): a small wood store built where somebody saw a
# shelter short of wood. Constants are world rules, not kernel limits.
BUILD_YARD = "build_yard"
GO_YARD = "go_yard"
TAKE_WOOD = "take_wood"
DEPOSIT_WOOD = "deposit_wood"
YARD_WOOD = 2          # wood a yard costs in total
YARD_WORK = 4          # work ticks to finish a yard
YARD_CAPACITY = 6      # a yard is "full" at this stock; the kernel itself has no cap
YARD_RANGE = 6         # no second yard within this many steps of a known one


def wood_cost(work_done: int) -> int:
    """Pay one wood before starting each group of four work ticks."""
    return int(work_done % WORK_PER_WOOD == 0)


def remaining_wood(work_done: int, build_ticks: int) -> int:
    return (build_ticks + WORK_PER_WOOD - 1) // WORK_PER_WOOD - (
        work_done + WORK_PER_WOOD - 1) // WORK_PER_WOOD


def yard_cost(work_done: int) -> int:
    """Pay one wood before yard work ticks 0 and 2."""
    return int(work_done in (0, 2))


def remaining_yard_wood(work_done: int) -> int:
    return sum(yard_cost(step) for step in range(work_done, YARD_WORK))


def yard_id(site: tuple[int, int]) -> str:
    return f"yard-{site[0]}-{site[1]}"
