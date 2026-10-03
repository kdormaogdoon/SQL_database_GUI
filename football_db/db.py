"""SQLite-backed database: generic table creation, roster rules, stats, analytics."""
import re
import sqlite3

from . import positions as pos

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SQL_TYPES = ("INTEGER", "REAL", "TEXT", "BLOB", "NUMERIC")
READ_ONLY_PREFIXES = ("select", "with", "pragma", "explain")
AGGREGATES = ("SUM", "AVG", "MAX", "MIN", "COUNT")


class RosterRuleError(ValueError):
    """Raised when adding/updating a player would violate a roster rule."""


def ident(name):
    """Validate an SQL identifier (table/column name) and return it quoted."""
    if not isinstance(name, str) or not _IDENT.match(name):
        raise ValueError(f"invalid identifier {name!r}")
    return f'"{name}"'


class Database:
    def __init__(self, path=":memory:"):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.create_football_schema()

    # ---------- generic table creation ----------
    def create_table(self, name, columns, if_not_exists=True):
        """columns: list of (name, type[, constraints]) tuples, e.g.
        [("id", "INTEGER", "PRIMARY KEY"), ("name", "TEXT", "NOT NULL")]"""
        if not columns:
            raise ValueError("a table needs at least one column")
        parts = []
        for col in columns:
            cname, ctype, *rest = col
            if ctype.upper() not in SQL_TYPES:
                raise ValueError(f"unsupported type {ctype!r}")
            extra = rest[0].strip() if rest and rest[0] else ""
            if not re.fullmatch(r"[A-Za-z0-9_ ()'\".,]*", extra):
                raise ValueError(f"unsafe column constraint {extra!r}")
            parts.append(f"{ident(cname)} {ctype.upper()} {extra}".strip())
        ine = "IF NOT EXISTS " if if_not_exists else ""
        with self.conn:
            self.conn.execute(f"CREATE TABLE {ine}{ident(name)} ({', '.join(parts)})")

    def tables(self):
        rows = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
        return [r[0] for r in rows]

    def columns(self, table):
        rows = self.conn.execute(f"PRAGMA table_info({ident(table)})").fetchall()
        return [(r["name"], r["type"]) for r in rows]

    def insert(self, table, row):
        cols = list(row)
        sql = (f"INSERT INTO {ident(table)} ({', '.join(map(ident, cols))}) "
               f"VALUES ({', '.join('?' * len(cols))})")
        with self.conn:
            return self.conn.execute(sql, [row[c] for c in cols]).lastrowid

    # ---------- football schema ----------
    def create_football_schema(self):
        with self.conn:
            self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS teams (
                team_id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, city TEXT);
            CREATE TABLE IF NOT EXISTS players (
                player_id INTEGER PRIMARY KEY,
                team_id INTEGER NOT NULL REFERENCES teams(team_id),
                name TEXT NOT NULL,
                position TEXT NOT NULL,
                jersey INTEGER NOT NULL,
                UNIQUE (team_id, jersey));
            CREATE TABLE IF NOT EXISTS player_attributes (
                player_id INTEGER NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
                attribute TEXT NOT NULL,
                value REAL NOT NULL,
                PRIMARY KEY (player_id, attribute));
            CREATE TABLE IF NOT EXISTS games (
                game_id INTEGER PRIMARY KEY, season INTEGER, week INTEGER,
                home_team_id INTEGER REFERENCES teams(team_id),
                away_team_id INTEGER REFERENCES teams(team_id),
                home_score INTEGER, away_score INTEGER);
            -- long-format statistics: one row per (entity, game, stat)
            CREATE TABLE IF NOT EXISTS stats (
                stat_id INTEGER PRIMARY KEY,
                entity_type TEXT NOT NULL CHECK (entity_type IN ('player','team','game')),
                entity_id INTEGER NOT NULL,
                game_id INTEGER REFERENCES games(game_id),
                stat TEXT NOT NULL,
                value REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_stats ON stats(entity_type, stat, entity_id);
            """)

    # ---------- teams / players with roster rules ----------
    def add_team(self, name, city=None):
        return self.insert("teams", {"name": name, "city": city})

    def check_player(self, team_id, position, jersey, exclude_player=None):
        if position not in pos.POSITIONS:
            raise RosterRuleError(f"unknown position {position!r}")
        if not pos.jersey_ok(position, jersey):
            raise RosterRuleError(f"jersey {jersey} not allowed for {position}: {pos.JERSEY_RANGES[position]}")
        excl = exclude_player if exclude_player is not None else -1
        q = "SELECT COUNT(*) FROM players WHERE team_id=? AND player_id<>?"
        if self.conn.execute(q, (team_id, excl)).fetchone()[0] >= pos.MAX_ROSTER:
            raise RosterRuleError(f"roster is full ({pos.MAX_ROSTER})")
        q += " AND position=?"
        if self.conn.execute(q, (team_id, excl, position)).fetchone()[0] >= pos.POSITION_LIMITS[position][1]:
            raise RosterRuleError(f"too many {position} (max {pos.POSITION_LIMITS[position][1]})")
        if self.conn.execute("SELECT 1 FROM players WHERE team_id=? AND jersey=? AND player_id<>?",
                             (team_id, jersey, excl)).fetchone():
            raise RosterRuleError(f"jersey {jersey} already taken on this team")

    def add_player(self, team_id, name, position, jersey, attributes=None):
        """Insert a player after validating roster rules and attribute names/ranges."""
        self.check_player(team_id, position, jersey)
        allowed = pos.attributes_for(position)
        attributes = attributes or {}
        for k, v in attributes.items():
            if k not in allowed:
                raise RosterRuleError(f"attribute {k!r} not valid for {position}")
            lo, hi, _ = allowed[k]
            if not lo <= v <= hi:
                raise RosterRuleError(f"{k}={v} outside range [{lo}, {hi}]")
        with self.conn:
            pid = self.conn.execute(
                "INSERT INTO players (team_id, name, position, jersey) VALUES (?,?,?,?)",
                (team_id, name, position, jersey)).lastrowid
            self.conn.executemany(
                "INSERT INTO player_attributes VALUES (?,?,?)",
                [(pid, k, v) for k, v in attributes.items()])
        return pid

    def roster_report(self, team_id):
        """Per-position count vs. limits, flagging positions under the recommended minimum."""
        counts = {r["position"]: r["n"] for r in self.conn.execute(
            "SELECT position, COUNT(*) n FROM players WHERE team_id=? GROUP BY position", (team_id,))}
        out = []
        for p, (lo, hi) in pos.POSITION_LIMITS.items():
            n = counts.get(p, 0)
            out.append({"position": p, "count": n, "min": lo, "max": hi, "ok": lo <= n <= hi})
        return out

    # ---------- conditional attribute extraction ----------
    def players_with_attributes(self, position, attributes, team_id=None):
        """Rows for players of `position` with only the chosen attributes as columns."""
        valid = pos.attributes_for(position)
        bad = [a for a in attributes if a not in valid]
        if bad:
            raise ValueError(f"attributes not valid for {position}: {bad}")
        sql, params = build_player_query(position, attributes, team_id)
        return self.conn.execute(sql, params).fetchall()

    # ---------- statistics & analytics ----------
    def add_game(self, season, week, home_team_id, away_team_id, home_score=None, away_score=None):
        return self.insert("games", dict(season=season, week=week, home_team_id=home_team_id,
                                         away_team_id=away_team_id, home_score=home_score,
                                         away_score=away_score))

    def add_stat(self, entity_type, entity_id, stat, value, game_id=None):
        return self.insert("stats", dict(entity_type=entity_type, entity_id=entity_id,
                                         game_id=game_id, stat=stat, value=value))

    def analytic(self, entity_type, stat, agg="SUM", season=None, limit=None):
        """Aggregate a stat per entity, e.g. analytic('player','pass_yards','AVG')."""
        agg = agg.upper()
        if agg not in AGGREGATES:
            raise ValueError(f"agg must be one of {AGGREGATES}")
        name_sql = {"player": "(SELECT name FROM players WHERE player_id=s.entity_id)",
                    "team": "(SELECT name FROM teams WHERE team_id=s.entity_id)",
                    "game": "CAST(s.entity_id AS TEXT)"}[entity_type]
        sql = (f"SELECT s.entity_id, {name_sql} AS label, {agg}(s.value) AS result, COUNT(*) AS n "
               "FROM stats s LEFT JOIN games g ON g.game_id=s.game_id "
               "WHERE s.entity_type=? AND s.stat=?")
        params = [entity_type, stat]
        if season is not None:
            sql += " AND g.season=?"
            params.append(season)
        sql += " GROUP BY s.entity_id ORDER BY result DESC"
        if limit:
            sql += f" LIMIT {int(limit)}"
        return self.conn.execute(sql, params).fetchall()

    # ---------- free-form queries ----------
    def query(self, sql, params=()):
        """Run a read-only statement; returns (column_names, rows)."""
        stripped = sql.strip().lstrip("(").lower()
        if not stripped.startswith(READ_ONLY_PREFIXES) or ";" in sql.strip().rstrip(";"):
            raise ValueError("only a single read-only SELECT/WITH/PRAGMA/EXPLAIN statement is allowed")
        cur = self.conn.execute(sql, params)
        return [d[0] for d in cur.description or []], [tuple(r) for r in cur.fetchall()]

    def close(self):
        self.conn.close()


def build_player_query(position, attributes, team_id=None):
    """Return (sql, params) pivoting chosen attributes into columns."""
    cols = ["p.player_id", "p.name", "p.position", "p.jersey"]
    for a in attributes:
        cols.append(f"MAX(CASE WHEN a.attribute = '{a}' THEN a.value END) AS {ident(a)}")
    for a in attributes:  # attribute names come from the catalog, but validate anyway
        ident(a)
    sql = ("SELECT " + ", ".join(cols) + " FROM players p "
           "LEFT JOIN player_attributes a ON a.player_id = p.player_id WHERE p.position = ?")
    params = [position]
    if team_id is not None:
        sql += " AND p.team_id = ?"
        params.append(team_id)
    sql += " GROUP BY p.player_id ORDER BY p.jersey"
    return sql, params
