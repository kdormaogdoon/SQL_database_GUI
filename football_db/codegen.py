"""Generate standalone Python snippets from GUI selections."""
import random

from . import positions as pos
from .db import ident, build_player_query

_DIST_CALL = {
    "normal": lambda p: f"random.gauss({p['mean']!r}, {p['std']!r})",
    "uniform": lambda p: f"random.uniform({p['low']!r}, {p['high']!r})",
    "triangular": lambda p: f"random.triangular({p['low']!r}, {p['high']!r}, {p['mode']!r})",
}


def sample_player(position, spec, rng=random):
    """Draw one player's attributes. spec: {attr: distribution}. Values are
    clamped to the attribute's catalog range and rounded to ints."""
    catalog = pos.attributes_for(position)
    out = {}
    for attr, dist in spec.items():
        lo, hi, _ = catalog[attr]
        out[attr] = int(round(min(hi, max(lo, dist.sample(rng)))))
    return out


def generate_player_snippet(position, spec, count=1):
    """Return source code for a standalone script that creates players of `position`
    whose attributes follow the chosen distributions. spec: {attr: distribution}."""
    catalog = pos.attributes_for(position)
    if not spec:
        raise ValueError("select at least one attribute")
    lines = [
        "import random",
        "",
        f"POSITION = {position!r}",
        "",
        "# attribute -> (distribution sampler, min, max)  [values are clamped and rounded]",
        "ATTRIBUTES = {",
    ]
    for attr, dist in spec.items():
        if attr not in catalog:
            raise ValueError(f"{attr!r} is not an attribute of {position}")
        lo, hi, _ = catalog[attr]
        call = _DIST_CALL[dist.kind](dist.params())
        lines.append(f"    {attr!r}: (lambda: {call}, {lo}, {hi}),  # {dist.kind}")
    lines += [
        "}",
        "",
        "",
        "def make_player(seed=None):",
        '    """Return a dict of attribute values for one random player."""',
        "    if seed is not None:",
        "        random.seed(seed)",
        "    player = {'position': POSITION}",
        "    for name, (draw, lo, hi) in ATTRIBUTES.items():",
        "        player[name] = int(round(min(hi, max(lo, draw()))))",
        "    return player",
        "",
        "",
        "if __name__ == '__main__':",
        f"    for _ in range({int(count)}):",
        "        print(make_player())",
        "",
    ]
    return "\n".join(lines)


def generate_query_snippet(position, attributes, db_path="football.db", team_id=None):
    """Source code that pulls the chosen attributes for a position with sqlite3."""
    sql, params = build_player_query(position, attributes, team_id)
    return (
        "import sqlite3\n\n"
        f"DB_PATH = {db_path!r}\n"
        f"SQL = {sql!r}\n"
        f"PARAMS = {params!r}\n\n"
        "conn = sqlite3.connect(DB_PATH)\n"
        "conn.row_factory = sqlite3.Row\n"
        "for row in conn.execute(SQL, PARAMS):\n"
        "    print(dict(row))\n"
        "conn.close()\n"
    )


def generate_table_snippet(name, columns, db_path="football.db"):
    """Source code that creates a table from a column list [(name, type[, constraints])]."""
    defs = []
    for col in columns:
        cname, ctype, *rest = col
        extra = rest[0] if rest and rest[0] else ""
        defs.append(f"{ident(cname)} {ctype.upper()} {extra}".strip())
    ddl = f"CREATE TABLE IF NOT EXISTS {ident(name)} ({', '.join(defs)})"
    return (
        "import sqlite3\n\n"
        f"DB_PATH = {db_path!r}\n"
        f"DDL = {ddl!r}\n\n"
        "with sqlite3.connect(DB_PATH) as conn:\n"
        "    conn.execute(DDL)\n"
    )


def generate_sql_snippet(sql, db_path="football.db"):
    """Source code that runs an arbitrary read-only query and prints the rows."""
    return (
        "import sqlite3\n\n"
        f"DB_PATH = {db_path!r}\n"
        f"SQL = {sql.strip()!r}\n\n"
        "conn = sqlite3.connect(DB_PATH)\n"
        "conn.row_factory = sqlite3.Row\n"
        "for row in conn.execute(SQL):\n"
        "    print(dict(row))\n"
        "conn.close()\n"
    )
