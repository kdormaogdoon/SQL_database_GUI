"""Position definitions, attribute catalog and roster rules.

Edit the dictionaries here to change the rules; nothing else hard-codes them.
"""

# name -> (min, max, unit)
COMMON_ATTRIBUTES = {
    "height_in": (62, 82, "in"),
    "weight_lb": (160, 360, "lb"),
    "age": (21, 40, "yr"),
    "speed": (40, 99, "rating"),
    "strength": (40, 99, "rating"),
    "agility": (40, 99, "rating"),
    "awareness": (40, 99, "rating"),
    "stamina": (40, 99, "rating"),
}

_R = (40, 99, "rating")
POSITION_ATTRIBUTES = {
    "QB": {"throw_power": _R, "throw_accuracy": _R, "pocket_presence": _R, "scrambling": _R},
    "RB": {"carrying": _R, "elusiveness": _R, "break_tackle": _R, "receiving": _R},
    "WR": {"catching": _R, "route_running": _R, "release": _R, "jumping": _R},
    "TE": {"catching": _R, "run_blocking": _R, "route_running": _R},
    "OL": {"pass_block": _R, "run_block": _R, "impact_block": _R},
    "DL": {"pass_rush": _R, "block_shedding": _R, "tackling": _R},
    "LB": {"tackling": _R, "pursuit": _R, "pass_coverage": _R, "block_shedding": _R},
    "CB": {"man_coverage": _R, "zone_coverage": _R, "press": _R, "ball_skills": _R},
    "S": {"zone_coverage": _R, "tackling": _R, "pursuit": _R, "ball_skills": _R},
    "K": {"kick_power": _R, "kick_accuracy": _R},
    "P": {"kick_power": _R, "kick_accuracy": _R},
}
POSITIONS = tuple(POSITION_ATTRIBUTES)

# Roster rules
MAX_ROSTER = 53
POSITION_LIMITS = {  # (min recommended, max allowed)
    "QB": (2, 4), "RB": (3, 6), "WR": (4, 8), "TE": (2, 5), "OL": (7, 11),
    "DL": (6, 10), "LB": (4, 8), "CB": (4, 7), "S": (3, 5), "K": (1, 2), "P": (1, 2),
}
JERSEY_RANGES = {
    "QB": [(1, 19)], "RB": [(20, 49)], "WR": [(10, 19), (80, 89)], "TE": [(40, 49), (80, 89)],
    "OL": [(50, 79)], "DL": [(50, 79), (90, 99)], "LB": [(50, 59), (90, 99)],
    "CB": [(20, 49)], "S": [(20, 49)], "K": [(1, 19)], "P": [(1, 19)],
}


def attributes_for(position):
    """Ordered {attribute: (min, max, unit)} for a position (common + specific)."""
    if position not in POSITION_ATTRIBUTES:
        raise ValueError(f"unknown position {position!r}")
    return {**COMMON_ATTRIBUTES, **POSITION_ATTRIBUTES[position]}


def jersey_ok(position, number):
    return any(lo <= number <= hi for lo, hi in JERSEY_RANGES[position])
