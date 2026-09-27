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


def wood_cost(work_done: int) -> int:
    """Pay one wood before starting each group of four work ticks."""
    return int(work_done % WORK_PER_WOOD == 0)


def remaining_wood(work_done: int, build_ticks: int) -> int:
    return (build_ticks + WORK_PER_WOOD - 1) // WORK_PER_WOOD - (
        work_done + WORK_PER_WOOD - 1) // WORK_PER_WOOD
