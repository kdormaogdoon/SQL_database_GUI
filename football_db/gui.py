"""tkinter front end. Run with:  python -m football_db"""
import random
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import codegen, positions as pos
from .db import AGGREGATES, SQL_TYPES, Database
from .distributions import DISTRIBUTIONS, default_for, from_spec


def make_tree(parent, height=10):
    frame = ttk.Frame(parent)
    tree = ttk.Treeview(frame, show="headings", height=height)
    sb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    sbx = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=sb.set, xscrollcommand=sbx.set)
    tree.grid(row=0, column=0, sticky="nsew")
    sb.grid(row=0, column=1, sticky="ns")
    sbx.grid(row=1, column=0, sticky="ew")
    frame.rowconfigure(0, weight=1)
    frame.columnconfigure(0, weight=1)
    return frame, tree


def fill_tree(tree, cols, rows):
    tree["columns"] = cols
    for c in cols:
        tree.heading(c, text=c)
        tree.column(c, width=100, anchor="w")
    tree.delete(*tree.get_children())
    for r in rows:
        tree.insert("", "end", values=tuple(r))


class App(ttk.Frame):
    def __init__(self, master, db_path=":memory:"):
        super().__init__(master, padding=6)
        self.db_path = db_path
        self.db = Database(db_path)
        self.pack(fill="both", expand=True)
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True)
        self.build_tables_tab()
        self.build_roster_tab()
        self.build_designer_tab()
        self.build_stats_tab()
        self.build_sql_tab()
        # shared code output
        box = ttk.LabelFrame(self, text="Generated Python snippet")
        box.pack(fill="both", expand=False, pady=(6, 0))
        self.code = tk.Text(box, height=12, font="TkFixedFont", wrap="none")
        self.code.pack(fill="both", expand=True, side="left")
        bar = ttk.Frame(box)
        bar.pack(side="right", fill="y")
        ttk.Button(bar, text="Copy", command=self.copy_code).pack(fill="x")
        ttk.Button(bar, text="Save .py…", command=self.save_code).pack(fill="x")
        self.status = tk.StringVar()
        ttk.Label(self, textvariable=self.status, anchor="w").pack(fill="x")
        self.refresh_all()

    # ---------- helpers ----------
    def show_code(self, text):
        self.code.delete("1.0", "end")
        self.code.insert("1.0", text)

    def copy_code(self):
        self.clipboard_clear()
        self.clipboard_append(self.code.get("1.0", "end-1c"))
        self.status.set("Snippet copied to clipboard")

    def save_code(self):
        path = filedialog.asksaveasfilename(defaultextension=".py")
        if path:
            with open(path, "w") as f:
                f.write(self.code.get("1.0", "end-1c"))

    def guard(self, fn):
        """Run fn, reporting errors in a dialog instead of crashing the GUI."""
        try:
            fn()
        except Exception as e:  # noqa: BLE001 - surface all errors to the user
            messagebox.showerror("Error", str(e))

    def team_id(self):
        sel = self.team_var.get()
        return int(sel.split(":")[0]) if sel else None

    def refresh_all(self):
        teams = self.db.conn.execute("SELECT team_id, name FROM teams ORDER BY team_id").fetchall()
        vals = [f"{t[0]}: {t[1]}" for t in teams]
        for cb in (self.team_cb, self.stat_team_cb):
            cb["values"] = vals
        if vals and not self.team_var.get():
            self.team_var.set(vals[0])
        self.refresh_tables()
        self.refresh_roster()

    # ---------- Tables tab ----------
    def build_tables_tab(self):
        f = ttk.Frame(self.nb, padding=6)
        self.nb.add(f, text="Tables")
        ttk.Label(f, text="Table name").grid(row=0, column=0, sticky="w")
        self.tbl_name = ttk.Entry(f)
        self.tbl_name.grid(row=0, column=1, sticky="ew")
        ttk.Label(f, text="Columns, one per line:  name TYPE [constraints]   "
                          f"(types: {', '.join(SQL_TYPES)})").grid(row=1, column=0, columnspan=2, sticky="w")
        self.tbl_cols = tk.Text(f, height=6, width=50)
        self.tbl_cols.insert("1.0", "id INTEGER PRIMARY KEY\nname TEXT NOT NULL")
        self.tbl_cols.grid(row=2, column=0, columnspan=2, sticky="ew")
        row = ttk.Frame(f)
        row.grid(row=3, column=0, columnspan=2, sticky="w", pady=4)
        ttk.Button(row, text="Create table", command=lambda: self.guard(self.create_table)).pack(side="left")
        ttk.Button(row, text="Show code", command=lambda: self.guard(self.table_code)).pack(side="left", padx=4)
        self.tbl_list = tk.Listbox(f, height=8)
        self.tbl_list.grid(row=4, column=0, sticky="nsew")
        self.tbl_list.bind("<<ListboxSelect>>", lambda e: self.preview_table())
        fr, self.tbl_preview = make_tree(f)
        fr.grid(row=4, column=1, sticky="nsew")
        f.columnconfigure(1, weight=1)
        f.rowconfigure(4, weight=1)

    def parse_columns(self):
        cols = []
        for line in self.tbl_cols.get("1.0", "end").splitlines():
            if line.strip():
                parts = line.split(None, 2)
                if len(parts) < 2:
                    raise ValueError(f"need 'name TYPE' in line: {line!r}")
                cols.append(tuple(parts))
        return cols

    def create_table(self):
        self.db.create_table(self.tbl_name.get().strip(), self.parse_columns())
        self.table_code()
        self.refresh_tables()
        self.status.set(f"Created table {self.tbl_name.get().strip()}")

    def table_code(self):
        self.show_code(codegen.generate_table_snippet(
            self.tbl_name.get().strip(), self.parse_columns(), self.db_path if self.db_path != ":memory:" else "football.db"))

    def refresh_tables(self):
        self.tbl_list.delete(0, "end")
        for t in self.db.tables():
            self.tbl_list.insert("end", t)

    def preview_table(self):
        sel = self.tbl_list.curselection()
        if sel:
            t = self.tbl_list.get(sel[0])
            from .db import ident
            cols, rows = self.db.query(f"SELECT * FROM {ident(t)} LIMIT 200")
            fill_tree(self.tbl_preview, cols, rows)

    # ---------- Roster tab ----------
    def build_roster_tab(self):
        f = ttk.Frame(self.nb, padding=6)
        self.nb.add(f, text="Roster")
        top = ttk.Frame(f)
        top.pack(fill="x")
        self.team_var = tk.StringVar()
        ttk.Label(top, text="Team").pack(side="left")
        self.team_cb = ttk.Combobox(top, textvariable=self.team_var, state="readonly", width=24)
        self.team_cb.pack(side="left", padx=4)
        self.team_cb.bind("<<ComboboxSelected>>", lambda e: self.refresh_roster())
        self.new_team = ttk.Entry(top, width=16)
        self.new_team.pack(side="left")
        ttk.Button(top, text="Add team", command=lambda: self.guard(self.add_team)).pack(side="left", padx=4)
        form = ttk.Frame(f)
        form.pack(fill="x", pady=4)
        self.p_name, self.p_pos, self.p_jersey = tk.StringVar(), tk.StringVar(value="QB"), tk.StringVar()
        for label, w in (("Name", ttk.Entry(form, textvariable=self.p_name, width=18)),
                         ("Pos", ttk.Combobox(form, textvariable=self.p_pos, values=pos.POSITIONS, width=5, state="readonly")),
                         ("Jersey", ttk.Entry(form, textvariable=self.p_jersey, width=5))):
            ttk.Label(form, text=label).pack(side="left")
            w.pack(side="left", padx=4)
        ttk.Button(form, text="Add player (no attrs)", command=lambda: self.guard(self.add_player)).pack(side="left")
        self.report_var = tk.StringVar()
        ttk.Label(f, textvariable=self.report_var, foreground="#555").pack(anchor="w")
        fr, self.roster_tree = make_tree(f, 14)
        fr.pack(fill="both", expand=True)

    def add_team(self):
        self.db.add_team(self.new_team.get().strip())
        self.team_var.set("")
        self.new_team.delete(0, "end")
        self.refresh_all()
        self.team_var.set(self.team_cb["values"][-1])
        self.refresh_roster()

    def add_player(self):
        self.db.add_player(self.team_id(), self.p_name.get().strip(), self.p_pos.get(), int(self.p_jersey.get()))
        self.refresh_roster()

    def refresh_roster(self):
        tid = self.team_id()
        if tid is None:
            return
        cols, rows = self.db.query(
            "SELECT player_id, name, position, jersey FROM players "
            f"WHERE team_id={int(tid)} ORDER BY position, jersey")
        fill_tree(self.roster_tree, cols, rows)
        short = [f"{r['position']}:{r['count']}" for r in self.db.roster_report(tid) if r["count"] or r["min"]]
        bad = [r["position"] for r in self.db.roster_report(tid) if not r["ok"]]
        self.report_var.set(f"{len(rows)}/{pos.MAX_ROSTER} players  |  " + " ".join(short) +
                            (f"  |  outside recommended range: {', '.join(bad)}" if bad else ""))

    # ---------- Attribute designer tab ----------
    def build_designer_tab(self):
        f = ttk.Frame(self.nb, padding=6)
        self.nb.add(f, text="Attribute Designer")
        top = ttk.Frame(f)
        top.pack(fill="x")
        self.d_pos = tk.StringVar(value="QB")
        ttk.Label(top, text="Position").pack(side="left")
        cb = ttk.Combobox(top, textvariable=self.d_pos, values=pos.POSITIONS, state="readonly", width=6)
        cb.pack(side="left", padx=4)
        cb.bind("<<ComboboxSelected>>", lambda e: self.build_attr_rows())
        ttk.Label(top, text="Count").pack(side="left", padx=(12, 0))
        self.d_count = tk.StringVar(value="5")
        ttk.Entry(top, textvariable=self.d_count, width=4).pack(side="left", padx=4)
        btns = ttk.Frame(f)
        btns.pack(fill="x", pady=4)
        for text, fn in (("Generate player snippet", self.designer_player_code),
                         ("Generate query snippet", self.designer_query_code),
                         ("Preview query results", self.designer_preview),
                         ("Generate players into roster", self.designer_populate)):
            ttk.Button(btns, text=text, command=lambda fn=fn: self.guard(fn)).pack(side="left", padx=2)
        self.attr_frame = ttk.Frame(f)
        self.attr_frame.pack(fill="x")
        fr, self.designer_tree = make_tree(f, 6)
        fr.pack(fill="both", expand=True, pady=(6, 0))
        self.build_attr_rows()

    def build_attr_rows(self):
        for w in self.attr_frame.winfo_children():
            w.destroy()
        self.attr_rows = {}
        head = ("Use", "Attribute", "Range", "Distribution", "p1", "p2", "p3")
        for i, h in enumerate(head):
            ttk.Label(self.attr_frame, text=h, font="TkDefaultFont 9 bold").grid(row=0, column=i, padx=3)
        for r, (attr, (lo, hi, unit)) in enumerate(pos.attributes_for(self.d_pos.get()).items(), start=1):
            use, kind = tk.BooleanVar(), tk.StringVar(value="normal")
            ttk.Checkbutton(self.attr_frame, variable=use).grid(row=r, column=0)
            ttk.Label(self.attr_frame, text=attr).grid(row=r, column=1, sticky="w")
            ttk.Label(self.attr_frame, text=f"{lo}–{hi} {unit}").grid(row=r, column=2)
            c = ttk.Combobox(self.attr_frame, textvariable=kind, values=list(DISTRIBUTIONS), width=10, state="readonly")
            c.grid(row=r, column=3)
            entries = [ttk.Entry(self.attr_frame, width=7) for _ in range(3)]
            for j, e in enumerate(entries):
                e.grid(row=r, column=4 + j, padx=1)
            row = dict(use=use, kind=kind, entries=entries, lo=lo, hi=hi)
            self.attr_rows[attr] = row
            c.bind("<<ComboboxSelected>>", lambda e, a=attr: self.reset_params(a))
            self.reset_params(attr)

    def reset_params(self, attr):
        row = self.attr_rows[attr]
        dist = default_for(row["lo"], row["hi"], row["kind"].get())
        names = dist.param_names
        for j, e in enumerate(row["entries"]):
            e.config(state="normal")
            e.delete(0, "end")
            if j < len(names):
                e.insert(0, f"{dist.params()[names[j]]:.4g}")
                e.configure(foreground="black")
            else:
                e.config(state="disabled")
        row["names"] = names

    def selected_spec(self):
        spec = {}
        for attr, row in self.attr_rows.items():
            if row["use"].get():
                vals = {n: row["entries"][j].get() for j, n in enumerate(row["names"])}
                try:
                    spec[attr] = from_spec(row["kind"].get(), **vals)
                except ValueError as e:
                    raise ValueError(f"{attr}: {e}")
        if not spec:
            raise ValueError("Tick at least one attribute")
        return spec

    def designer_player_code(self):
        self.show_code(codegen.generate_player_snippet(
            self.d_pos.get(), self.selected_spec(), int(self.d_count.get())))

    def designer_query_code(self):
        self.show_code(codegen.generate_query_snippet(
            self.d_pos.get(), list(self.selected_spec()),
            self.db_path if self.db_path != ":memory:" else "football.db"))

    def designer_preview(self):
        rows = self.db.players_with_attributes(self.d_pos.get(), list(self.selected_spec()))
        cols = list(rows[0].keys()) if rows else ["player_id", "name", "position", "jersey"] + list(self.selected_spec())
        fill_tree(self.designer_tree, cols, rows)
        self.status.set(f"{len(rows)} {self.d_pos.get()} player(s)")

    def designer_populate(self):
        spec, position, tid = self.selected_spec(), self.d_pos.get(), self.team_id()
        if tid is None:
            raise ValueError("Add/select a team first (Roster tab)")
        used = {r[0] for r in self.db.conn.execute("SELECT jersey FROM players WHERE team_id=?", (tid,))}
        free = [n for lo, hi in pos.JERSEY_RANGES[position] for n in range(lo, hi + 1) if n not in used]
        added = 0
        for i in range(int(self.d_count.get())):
            if not free:
                break
            jersey = free.pop(0)
            attrs = codegen.sample_player(position, spec)
            try:
                self.db.add_player(tid, f"{position} Gen{random.randint(1000, 9999)}", position, jersey, attrs)
                added += 1
            except ValueError as e:
                self.status.set(f"Stopped after {added}: {e}")
                break
        self.refresh_roster()
        self.designer_preview()
        self.status.set(f"Added {added} generated {position}(s)")

    # ---------- Stats & analytics tab ----------
    def build_stats_tab(self):
        f = ttk.Frame(self.nb, padding=6)
        self.nb.add(f, text="Stats & Analytics")
        add = ttk.LabelFrame(f, text="Record a stat")
        add.pack(fill="x")
        self.s_type, self.s_id, self.s_stat, self.s_val, self.s_game = (
            tk.StringVar(value="player"), tk.StringVar(), tk.StringVar(), tk.StringVar(), tk.StringVar())
        for label, w in (("Entity", ttk.Combobox(add, textvariable=self.s_type, values=["player", "team", "game"], width=7, state="readonly")),
                         ("ID", ttk.Entry(add, textvariable=self.s_id, width=5)),
                         ("Stat", ttk.Entry(add, textvariable=self.s_stat, width=14)),
                         ("Value", ttk.Entry(add, textvariable=self.s_val, width=8)),
                         ("Game ID", ttk.Entry(add, textvariable=self.s_game, width=5))):
            ttk.Label(add, text=label).pack(side="left")
            w.pack(side="left", padx=3)
        ttk.Button(add, text="Add", command=lambda: self.guard(self.add_stat)).pack(side="left")
        g = ttk.LabelFrame(f, text="Add game (uses team selected on Roster tab as home; pick away below)")
        g.pack(fill="x", pady=4)
        self.stat_team_cb = ttk.Combobox(g, state="readonly", width=20)
        self.g_season, self.g_week = tk.StringVar(value="2026"), tk.StringVar(value="1")
        ttk.Label(g, text="Away").pack(side="left")
        self.stat_team_cb.pack(side="left", padx=3)
        for label, var in (("Season", self.g_season), ("Week", self.g_week)):
            ttk.Label(g, text=label).pack(side="left")
            ttk.Entry(g, textvariable=var, width=6).pack(side="left", padx=3)
        ttk.Button(g, text="Add game", command=lambda: self.guard(self.add_game)).pack(side="left")
        a = ttk.LabelFrame(f, text="Analytic")
        a.pack(fill="x")
        self.a_type, self.a_stat, self.a_agg, self.a_season = (
            tk.StringVar(value="player"), tk.StringVar(), tk.StringVar(value="SUM"), tk.StringVar())
        for label, w in (("Entity", ttk.Combobox(a, textvariable=self.a_type, values=["player", "team", "game"], width=7, state="readonly")),
                         ("Stat", ttk.Entry(a, textvariable=self.a_stat, width=14)),
                         ("Aggregate", ttk.Combobox(a, textvariable=self.a_agg, values=AGGREGATES, width=6, state="readonly")),
                         ("Season", ttk.Entry(a, textvariable=self.a_season, width=6))):
            ttk.Label(a, text=label).pack(side="left")
            w.pack(side="left", padx=3)
        ttk.Button(a, text="Run", command=lambda: self.guard(self.run_analytic)).pack(side="left")
        fr, self.stats_tree = make_tree(f, 12)
        fr.pack(fill="both", expand=True, pady=4)

    def add_stat(self):
        game = int(self.s_game.get()) if self.s_game.get().strip() else None
        self.db.add_stat(self.s_type.get(), int(self.s_id.get()), self.s_stat.get().strip(),
                         float(self.s_val.get()), game)
        self.status.set("Stat recorded")

    def add_game(self):
        away = self.stat_team_cb.get()
        if not away or self.team_id() is None:
            raise ValueError("Select a home team (Roster tab) and an away team")
        self.db.add_game(int(self.g_season.get()), int(self.g_week.get()), self.team_id(), int(away.split(":")[0]))
        self.status.set("Game added")

    def run_analytic(self):
        season = int(self.a_season.get()) if self.a_season.get().strip() else None
        rows = self.db.analytic(self.a_type.get(), self.a_stat.get().strip(), self.a_agg.get(), season)
        fill_tree(self.stats_tree, ["entity_id", "label", self.a_agg.get().lower(), "n"], [tuple(r) for r in rows])
        self.show_code(codegen.generate_sql_snippet(
            "SELECT entity_id, SUM(value) FROM stats WHERE entity_type = "
            f"'{self.a_type.get()}' AND stat = '{self.a_stat.get().strip()}' GROUP BY entity_id"
            .replace("SUM", self.a_agg.get())))

    # ---------- SQL tab ----------
    def build_sql_tab(self):
        f = ttk.Frame(self.nb, padding=6)
        self.nb.add(f, text="SQL Query")
        self.sql = tk.Text(f, height=5)
        self.sql.insert("1.0", "SELECT position, COUNT(*) AS n FROM players GROUP BY position")
        self.sql.pack(fill="x")
        row = ttk.Frame(f)
        row.pack(fill="x", pady=4)
        ttk.Button(row, text="Run", command=lambda: self.guard(self.run_sql)).pack(side="left")
        ttk.Button(row, text="Python snippet", command=lambda: self.guard(self.sql_code)).pack(side="left", padx=4)
        fr, self.sql_tree = make_tree(f, 14)
        fr.pack(fill="both", expand=True)

    def run_sql(self):
        cols, rows = self.db.query(self.sql.get("1.0", "end"))
        fill_tree(self.sql_tree, cols, rows)
        self.status.set(f"{len(rows)} row(s)")

    def sql_code(self):
        sql = self.sql.get("1.0", "end")
        self.db.query(sql)  # validates read-only
        self.show_code(codegen.generate_sql_snippet(sql, self.db_path if self.db_path != ":memory:" else "football.db"))


def main(argv=None):
    import sys
    path = (argv or sys.argv[1:] or [":memory:"])[0]
    root = tk.Tk()
    root.title("Football Database")
    root.geometry("980x760")
    App(root, path)
    root.mainloop()
