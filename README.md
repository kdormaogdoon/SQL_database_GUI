# Football Database GUI

SQLite + tkinter tool for building football rosters, stats, analytics, and
generating reusable Python snippets. Standard library only (tkinter ships with
most Python installs; `apt install python3-tk` on Debian/Ubuntu).

    python -m football_db [path/to/file.db]     # omit path for an in-memory DB

## Tabs
- **Tables** – define any table (name + `column TYPE constraints` lines); get a `CREATE TABLE` snippet.
- **Roster** – teams and players, with rules enforced (53-man cap, per-position max, legal jersey ranges, unique jerseys).
- **Attribute Designer** – pick a position, tick the attributes you want, assign each a
  Normal / Uniform / Triangular distribution (parameters editable), then:
  generate a standalone player-spec snippet, a SQL/sqlite3 query snippet, preview matching
  players, or generate players straight into the roster.
- **Stats & Analytics** – long-format `stats` table (player/team/game entities, per game);
  aggregate with SUM/AVG/MAX/MIN/COUNT, optionally per season.
- **SQL Query** – read-only SQL runner with "Python snippet" export.

## Customizing
Positions, attributes, ranges, and roster rules live in `football_db/positions.py`.
The core (`Database`, distributions, `codegen`) has no GUI dependency and can be used directly:

    from football_db import Database, Normal, generate_player_snippet
    print(generate_player_snippet("QB", {"throw_power": Normal(80, 6)}))

Tests: `pip install pytest && pytest`.
