import random
import pytest
from football_db import Database, RosterRuleError, Normal, Uniform, Triangular, from_spec
from football_db import codegen


@pytest.fixture
def db():
    d = Database()
    d.team = d.add_team("Hawks", "Seattle")
    return d


def test_roster_rules(db):
    db.add_player(db.team, "A", "QB", 12)
    with pytest.raises(RosterRuleError):
        db.add_player(db.team, "B", "QB", 12)        # duplicate jersey
    with pytest.raises(RosterRuleError):
        db.add_player(db.team, "C", "QB", 60)        # jersey out of range
    for n in (1, 2, 3):
        db.add_player(db.team, f"Q{n}", "QB", n)
    with pytest.raises(RosterRuleError):
        db.add_player(db.team, "X", "QB", 4)         # position cap (4)
    with pytest.raises(RosterRuleError):
        db.add_player(db.team, "Y", "WR", 85, {"throw_power": 80})  # wrong attribute
    with pytest.raises(RosterRuleError):
        db.add_player(db.team, "Z", "WR", 86, {"speed": 120})       # out of range


def test_conditional_extraction(db):
    db.add_player(db.team, "A", "QB", 12, {"throw_power": 90, "speed": 60, "age": 30})
    db.add_player(db.team, "W", "WR", 81, {"catching": 88})
    rows = db.players_with_attributes("QB", ["throw_power", "age"])
    assert len(rows) == 1 and dict(rows[0])["throw_power"] == 90
    assert "speed" not in rows[0].keys()
    with pytest.raises(ValueError):
        db.players_with_attributes("QB", ["catching"])


def test_stats_analytics(db):
    t2 = db.add_team("Owls")
    p = db.add_player(db.team, "A", "QB", 12)
    g1, g2 = db.add_game(2025, 1, db.team, t2), db.add_game(2026, 1, db.team, t2)
    db.add_stat("player", p, "pass_yards", 300, g1)
    db.add_stat("player", p, "pass_yards", 100, g2)
    assert db.analytic("player", "pass_yards", "SUM")[0]["result"] == 400
    assert db.analytic("player", "pass_yards", "AVG", season=2025)[0]["result"] == 300
    with pytest.raises(ValueError):
        db.analytic("player", "x", "DROP")


def test_generic_table_and_query(db):
    db.create_table("coaches", [("id", "INTEGER", "PRIMARY KEY"), ("name", "TEXT", "NOT NULL")])
    db.insert("coaches", {"id": 1, "name": "Pat"})
    assert db.query("SELECT * FROM coaches")[1] == [(1, "Pat")]
    with pytest.raises(ValueError):
        db.query("DELETE FROM coaches")
    with pytest.raises(ValueError):
        db.query("SELECT 1; DROP TABLE coaches")
    with pytest.raises(ValueError):
        db.create_table("bad name", [("a", "TEXT")])
    with pytest.raises(ValueError):
        db.create_table("t", [("a", "TEXT", "); DROP TABLE x; --")])


def test_distributions_validate():
    assert from_spec("triangular", low=1, mode=2, high=3)
    with pytest.raises(ValueError):
        from_spec("triangular", low=1, mode=5, high=3)
    with pytest.raises(ValueError):
        from_spec("poisson", lam=1)


def test_generated_snippet_runs_and_respects_ranges():
    spec = {"throw_power": Normal(80, 20), "speed": Uniform(40, 99), "age": Triangular(21, 27, 40)}
    code = codegen.generate_player_snippet("QB", spec, count=3)
    ns = {"__name__": "snippet"}
    exec(compile(code, "snippet", "exec"), ns)
    for seed in range(200):
        p = ns["make_player"](seed)
        assert p["position"] == "QB"
        assert 40 <= p["throw_power"] <= 99 and 21 <= p["age"] <= 40
    # in-package sampler also usable with the DB
    d = Database(); t = d.add_team("T")
    attrs = codegen.sample_player("QB", spec, random.Random(1))
    d.add_player(t, "Gen", "QB", 7, attrs)


def test_query_and_table_snippets(db, tmp_path):
    db.add_player(db.team, "A", "QB", 12, {"throw_power": 90})
    path = tmp_path / "f.db"
    import sqlite3
    disk = sqlite3.connect(path); db.conn.backup(disk); disk.close()
    code = codegen.generate_query_snippet("QB", ["throw_power"], str(path))
    exec(compile(code, "q", "exec"), {})
    ns = {}
    exec(compile(codegen.generate_table_snippet("c", [("id", "INTEGER", "PRIMARY KEY")], str(tmp_path / "n.db")), "t", "exec"), ns)
