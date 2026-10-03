"""Football roster / stats database with a tkinter GUI and code generation."""
from .db import Database, RosterRuleError
from .distributions import Normal, Uniform, Triangular, from_spec
from .codegen import generate_player_snippet, generate_query_snippet, generate_table_snippet

__all__ = [
    "Database", "RosterRuleError", "Normal", "Uniform", "Triangular", "from_spec",
    "generate_player_snippet", "generate_query_snippet", "generate_table_snippet",
]
