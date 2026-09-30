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

# Stone and the basic stone axe (stone on, axe on). Stone is finite for now.
STONE = "stone"
GO_STONE = "go_stone"
GATHER_STONE = "gather_stone"
CRAFT_AXE = "craft_axe"
STONE_STOCK = 8        # one outcrop, no renewal in this slice
STONE_PACK = 1
AXE_WOOD_PACK = 5      # an axe holder gathers this much wood per claim instead of WOOD_PACK
AXE_WORK = 3           # craft ticks at the crafter's own finished shelter
AXE_TIMEOUT = 60       # a plan that has collected no stone this long after starting is given up


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


def wood_pack(has_axe: bool) -> int:
    return AXE_WOOD_PACK if has_axe else WOOD_PACK


def axe_cost(craft_done: int) -> tuple[str, int] | None:
    """One wood before craft tick 0, one stone before craft tick 1, nothing before tick 2."""
    return {0: (WOOD, 1), 1: (STONE, 1)}.get(craft_done)
