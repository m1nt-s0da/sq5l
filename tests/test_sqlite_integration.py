import sqlite3
import pytest

from sq5l import asterisk, param, table

SQLITE_SUPPORTS_RIGHT_FULL = sqlite3.sqlite_version_info >= (3, 39, 0)


def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    return con


def test_select_where_order_range_runs_on_sqlite() -> None:
    con = _conn()
    con.executescript("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            age INTEGER NOT NULL,
            deleted_at TEXT,
            created_at INTEGER NOT NULL
        );
        """)
    con.executemany(
        "INSERT INTO users (id, name, age, deleted_at, created_at) VALUES (?, ?, ?, ?, ?)",
        [
            (1, "Mike", 31, None, 100),
            (2, "Micah", 35, None, 90),
            (3, "Miki", 22, None, 110),
            (4, "Mike", 50, "2024-01-01", 80),
        ],
    )

    q, p = (
        table("users")
        .where(
            lambda users: users.name.like(param("Mic%"))
            & (users.age >= param(30))
            & (users.deleted_at == None)
        )
        .order(("created_at", "desc"))
        .select("id", "name")
        .query()
    )

    rows = con.execute(q, p).fetchall()
    assert [tuple(r) for r in rows] == [(2, "Micah")]


def test_chained_where_runs_on_sqlite() -> None:
    con = _conn()
    con.executescript("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            age INTEGER NOT NULL
        );
        """)
    con.executemany(
        "INSERT INTO users (id, name, age) VALUES (?, ?, ?)",
        [
            (1, "Miki", 22),
            (2, "Micah", 35),
            (3, "Mike", 31),
            (4, "Bob", 44),
        ],
    )

    q, p = (
        table("users")
        .where(lambda users: users.name.like(param("Mi%")))
        .where(lambda users: users.age >= param(30))
        .order(("id", "asc"))
        .select("id", "name")
        .query()
    )

    rows = con.execute(q, p).fetchall()
    assert [tuple(r) for r in rows] == [(2, "Micah"), (3, "Mike")]
    assert p == ("Mi%", 30)


def test_range_clause_runs_on_sqlite() -> None:
    con = _conn()
    con.executescript("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            created_at INTEGER NOT NULL
        );
        """)
    con.executemany(
        "INSERT INTO users (id, name, created_at) VALUES (?, ?, ?)",
        [
            (1, "A", 100),
            (2, "B", 200),
            (3, "C", 300),
            (4, "D", 400),
        ],
    )

    q, p = (
        table("users")
        .order(("created_at", "asc"))
        .range(offset=1, limit=2)
        .select("id", "name")
        .query()
    )

    rows = con.execute(q, p).fetchall()
    assert [tuple(r) for r in rows] == [(2, "B"), (3, "C")]


def test_insert_select_runs_on_sqlite() -> None:
    con = _conn()
    con.executescript("""
        CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL, age INTEGER NOT NULL);
        CREATE TABLE teen_users (name TEXT NOT NULL, age INTEGER NOT NULL);
        """)
    con.executemany(
        "INSERT INTO users (id, name, age) VALUES (?, ?, ?)",
        [(1, "Alice", 19), (2, "Bob", 20), (3, "Caro", 15)],
    )

    q, p = (
        table("teen_users")
        .insert(
            ("name", "age"),
            table("users")
            .where(lambda users: users.age < param(20))
            .select("name", "age"),
        )
        .query()
    )

    con.execute(q, p)
    rows = con.execute("SELECT name, age FROM teen_users ORDER BY name").fetchall()
    assert [tuple(r) for r in rows] == [("Alice", 19), ("Caro", 15)]


def test_update_with_scalar_subquery_runs_on_sqlite() -> None:
    con = _conn()
    con.executescript("""
        CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
        CREATE TABLE user_update_batch (user_id INTEGER PRIMARY KEY, name TEXT NOT NULL);
        """)
    con.executemany(
        "INSERT INTO users (id, name) VALUES (?, ?)",
        [(1, "Old1"), (2, "Old2"), (10, "Old10")],
    )
    con.executemany(
        "INSERT INTO user_update_batch (user_id, name) VALUES (?, ?)",
        [(1, "New1"), (2, "New2"), (10, "New10")],
    )

    q, p = (
        table("users")
        .where(lambda users: users.id < param(10))
        .update(
            "name",
            lambda users: table("user_update_batch", as_="b")
            .where(lambda b: users.id == b.user_id)
            .select("name"),
        )
        .query()
    )

    con.execute(q, p)
    rows = con.execute("SELECT id, name FROM users ORDER BY id").fetchall()
    assert [tuple(r) for r in rows] == [(1, "New1"), (2, "New2"), (10, "Old10")]


def test_derived_table_alias_runs_on_sqlite() -> None:
    con = _conn()
    con.executescript("""
        CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL);
        """)
    con.executemany(
        "INSERT INTO orders (id, user_id) VALUES (?, ?)",
        [(1, 10), (2, 10), (3, 10), (4, 20), (5, 20)],
    )

    q, p = (
        table("orders", as_="o")
        .group_by(lambda o: o.user_id)
        .select(lambda o: o.user_id, lambda: asterisk.count().as_("order_count"))
        .as_("t")
        .where(lambda t: t.order_count >= param(3))
        .select(lambda t: t.user_id, lambda t: t.order_count)
        .query()
    )

    rows = con.execute(q, p).fetchall()
    assert [tuple(r) for r in rows] == [(10, 3)]


def test_join_select_runs_on_sqlite() -> None:
    con = _conn()
    con.executescript("""
        CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
        CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, total INTEGER NOT NULL);
        """)
    con.executemany(
        "INSERT INTO users (id, name) VALUES (?, ?)",
        [(1, "Alice"), (2, "Bob")],
    )
    con.executemany(
        "INSERT INTO orders (id, user_id, total) VALUES (?, ?, ?)",
        [(10, 1, 5000), (11, 2, 2000)],
    )

    q, p = (
        table("users", as_="u")
        .inner_join(table("orders", as_="o"), on=lambda u, o: o.user_id == u.id)
        .where(lambda o: o.total >= param(3000))
        .select(lambda u: u.id, lambda u: u.name, lambda o: o.id.as_("order_id"))
        .query()
    )

    rows = con.execute(q, p).fetchall()
    assert [tuple(r) for r in rows] == [(1, "Alice", 10)]


def test_left_join_runs_on_sqlite() -> None:
    con = _conn()
    con.executescript("""
        CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
        CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, total INTEGER NOT NULL);
        """)
    con.executemany(
        "INSERT INTO users (id, name) VALUES (?, ?)",
        [(1, "Alice"), (2, "Bob"), (3, "Carol")],
    )
    con.executemany(
        "INSERT INTO orders (id, user_id, total) VALUES (?, ?, ?)",
        [(10, 1, 5000), (11, 2, 2000)],
    )

    q, p = (
        table("users", as_="u")
        .left_join(table("orders", as_="o"), on=lambda u, o: o.user_id == u.id)
        .where(lambda o: o.id == None)
        .select(lambda u: u.id, lambda u: u.name)
        .query()
    )

    rows = con.execute(q, p).fetchall()
    assert [tuple(r) for r in rows] == [(3, "Carol")]


def test_cross_join_runs_on_sqlite() -> None:
    con = _conn()
    con.executescript("""
        CREATE TABLE a (id INTEGER PRIMARY KEY, label TEXT NOT NULL);
        CREATE TABLE b (id INTEGER PRIMARY KEY, code TEXT NOT NULL);
        """)
    con.executemany(
        "INSERT INTO a (id, label) VALUES (?, ?)",
        [(1, "A1"), (2, "A2")],
    )
    con.executemany(
        "INSERT INTO b (id, code) VALUES (?, ?)",
        [(10, "B10"), (20, "B20")],
    )

    q, p = (
        table("a", as_="a")
        .cross_join(table("b", as_="b"))
        .order((lambda a: a.id, "asc"), (lambda b: b.id, "asc"))
        .select(lambda a: a.id, lambda b: b.id)
        .query()
    )

    rows = con.execute(q, p).fetchall()
    assert [tuple(r) for r in rows] == [(1, 10), (1, 20), (2, 10), (2, 20)]


def test_right_and_full_join_sql_generation() -> None:
    q_right, p_right = (
        table("users", as_="u")
        .right_join(table("orders", as_="o"), on=lambda u, o: o.user_id == u.id)
        .select(lambda u: u.id, lambda o: o.id)
        .query()
    )
    assert " RIGHT JOIN " in q_right
    assert p_right == ()

    q_full, p_full = (
        table("users", as_="u")
        .full_join(table("orders", as_="o"), on=lambda u, o: o.user_id == u.id)
        .select(lambda u: u.id, lambda o: o.id)
        .query()
    )
    assert " FULL OUTER JOIN " in q_full
    assert p_full == ()


@pytest.mark.skipif(
    not SQLITE_SUPPORTS_RIGHT_FULL,
    reason="SQLite >= 3.39.0 is required for RIGHT/FULL OUTER JOIN execution",
)
def test_right_join_runs_on_supported_sqlite() -> None:
    con = _conn()
    con.executescript("""
        CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
        CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL);
        """)
    con.executemany(
        "INSERT INTO users (id, name) VALUES (?, ?)",
        [(1, "Alice"), (2, "Bob")],
    )
    con.executemany(
        "INSERT INTO orders (id, user_id) VALUES (?, ?)",
        [(10, 1), (11, 3)],
    )

    q, p = (
        table("users", as_="u")
        .right_join(table("orders", as_="o"), on=lambda u, o: o.user_id == u.id)
        .order((lambda o: o.id, "asc"))
        .select(lambda u: u.id.as_("user_id"), lambda o: o.id.as_("order_id"))
        .query()
    )

    rows = con.execute(q, p).fetchall()
    assert [tuple(r) for r in rows] == [(1, 10), (None, 11)]


@pytest.mark.skipif(
    not SQLITE_SUPPORTS_RIGHT_FULL,
    reason="SQLite >= 3.39.0 is required for RIGHT/FULL OUTER JOIN execution",
)
def test_full_outer_join_runs_on_supported_sqlite() -> None:
    con = _conn()
    con.executescript("""
        CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
        CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL);
        """)
    con.executemany(
        "INSERT INTO users (id, name) VALUES (?, ?)",
        [(1, "Alice"), (2, "Bob")],
    )
    con.executemany(
        "INSERT INTO orders (id, user_id) VALUES (?, ?)",
        [(10, 1), (11, 3)],
    )

    q, p = (
        table("users", as_="u")
        .full_join(table("orders", as_="o"), on=lambda u, o: o.user_id == u.id)
        .order((lambda o: o.id, "asc"))
        .select(lambda u: u.id.as_("user_id"), lambda o: o.id.as_("order_id"))
        .query()
    )

    rows = con.execute(q, p).fetchall()
    assert set(tuple(r) for r in rows) == {(1, 10), (None, 11), (2, None)}


def test_group_by_having_runs_on_sqlite() -> None:
    con = _conn()
    con.executescript("""
        CREATE TABLE payments (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            done_at TEXT
        );
        """)
    con.executemany(
        "INSERT INTO payments (id, user_id, amount, done_at) VALUES (?, ?, ?, ?)",
        [
            (1, 10, 2000, "2024-01-01"),
            (2, 10, 2500, "2024-01-02"),
            (3, 10, 3000, "2024-01-03"),
            (4, 20, 1500, "2024-01-01"),
            (5, 20, 1600, None),
        ],
    )

    q, p = (
        table("payments")
        .where(lambda payments: payments.done_at != None)
        .group_by(
            "user_id",
            having=lambda payments: (asterisk.count() >= param(3))
            & (payments.amount.avg() >= param(2000)),
        )
        .select(
            "user_id",
            lambda: asterisk.count().as_("cnt"),
            lambda payments: payments.amount.avg().as_("avg_amount"),
        )
        .query()
    )

    rows = con.execute(q, p).fetchall()
    assert [tuple(r) for r in rows] == [(10, 3, 2500.0)]


def test_distinct_select_runs_on_sqlite() -> None:
    con = _conn()
    con.executescript("""
        CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
        """)
    con.executemany(
        "INSERT INTO users (id, name) VALUES (?, ?)",
        [(1, "A"), (2, "A"), (3, "B")],
    )

    q, p = table("users").select("name", distinct=True).query()
    rows = con.execute(q, p).fetchall()
    assert [tuple(r) for r in rows] == [("A",), ("B",)]


def test_insert_values_runs_on_sqlite() -> None:
    con = _conn()
    con.executescript("""
        CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL, age INTEGER NOT NULL);
        """)

    q, p = table("users").insert({"name": "Mike", "age": 15}).query()
    con.execute(q, p)

    rows = con.execute("SELECT name, age FROM users").fetchall()
    assert [tuple(r) for r in rows] == [("Mike", 15)]


def test_update_with_mapping_runs_on_sqlite() -> None:
    con = _conn()
    con.executescript("""
        CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
        """)
    con.executemany(
        "INSERT INTO users (id, name) VALUES (?, ?)",
        [(1, "Old1"), (2, "Old2")],
    )

    q, p = (
        table("users")
        .where(lambda users: users.id == param(2))
        .update({"name": "Updated"})
        .query()
    )
    con.execute(q, p)

    rows = con.execute("SELECT id, name FROM users ORDER BY id").fetchall()
    assert [tuple(r) for r in rows] == [(1, "Old1"), (2, "Updated")]


def test_update_with_chained_where_runs_on_sqlite() -> None:
    con = _conn()
    con.executescript("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            age INTEGER NOT NULL
        );
        """)
    con.executemany(
        "INSERT INTO users (id, name, age) VALUES (?, ?, ?)",
        [
            (1, "Miki", 22),
            (2, "Micah", 35),
            (3, "Mike", 31),
            (4, "Bob", 44),
        ],
    )

    q, p = (
        table("users")
        .where(lambda users: users.name.like(param("Mi%")))
        .where(lambda users: users.age >= param(30))
        .update({"name": "Matched"})
        .query()
    )

    con.execute(q, p)
    rows = con.execute("SELECT id, name FROM users ORDER BY id").fetchall()
    assert [tuple(r) for r in rows] == [
        (1, "Miki"),
        (2, "Matched"),
        (3, "Matched"),
        (4, "Bob"),
    ]
    assert p == ("Matched", "Mi%", 30)


def test_delete_with_chained_where_runs_on_sqlite() -> None:
    con = _conn()
    con.executescript("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            age INTEGER NOT NULL
        );
        """)
    con.executemany(
        "INSERT INTO users (id, name, age) VALUES (?, ?, ?)",
        [
            (1, "Miki", 22),
            (2, "Micah", 35),
            (3, "Mike", 31),
            (4, "Bob", 44),
        ],
    )

    q, p = (
        table("users")
        .where(lambda users: users.name.like(param("Mi%")))
        .where(lambda users: users.age >= param(30))
        .delete()
        .query()
    )

    con.execute(q, p)
    rows = con.execute("SELECT id, name FROM users ORDER BY id").fetchall()
    assert [tuple(r) for r in rows] == [(1, "Miki"), (4, "Bob")]
    assert p == ("Mi%", 30)


def test_exists_subquery_runs_on_sqlite() -> None:
    con = _conn()
    con.executescript("""
        CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
        CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, total INTEGER NOT NULL);
        """)
    con.executemany(
        "INSERT INTO users (id, name) VALUES (?, ?)",
        [(1, "Alice"), (2, "Bob")],
    )
    con.executemany(
        "INSERT INTO orders (id, user_id, total) VALUES (?, ?, ?)",
        [(1, 1, 4000), (2, 1, 2000), (3, 2, 1000)],
    )

    q, p = (
        table("users", as_="u")
        .where(
            lambda u: table("orders", as_="o")
            .where(lambda o: (o.user_id == u.id) & (o.total >= param(3000)))
            .exists()
        )
        .select(lambda u: u.id, lambda u: u.name)
        .query()
    )

    rows = con.execute(q, p).fetchall()
    assert [tuple(r) for r in rows] == [(1, "Alice")]


def test_scalar_string_functions_run_on_sqlite() -> None:
    con = _conn()
    con.executescript("""
        CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
        """)
    con.executemany(
        "INSERT INTO users (id, name) VALUES (?, ?)",
        [(1, "  MiKe  "), (2, "Bob")],
    )

    q, p = (
        table("users")
        .where(lambda users: users.id == param(1))
        .select(
            lambda users: users.name.trim().lower().as_("normalized_name"),
            lambda users: users.name.length().as_("name_len"),
            lambda users: users.name.replace(param("M"), param("X")).as_("replaced"),
            lambda users: users.name.substr(param(3), param(2)).as_("middle"),
        )
        .query()
    )

    row = con.execute(q, p).fetchone()
    assert tuple(row) == ("mike", 8, "  XiKe  ", "Mi")


def test_scalar_numeric_and_null_functions_run_on_sqlite() -> None:
    con = _conn()
    con.executescript("""
        CREATE TABLE metrics (id INTEGER PRIMARY KEY, value REAL, note TEXT);
        """)
    con.executemany(
        "INSERT INTO metrics (id, value, note) VALUES (?, ?, ?)",
        [(1, -10.75, None)],
    )

    q, p = (
        table("metrics")
        .where(lambda metrics: metrics.id == param(1))
        .select(
            lambda metrics: metrics.value.abs().as_("abs_value"),
            lambda metrics: metrics.value.round(param(1)).as_("rounded"),
            lambda metrics: metrics.note.ifnull(param("n/a")).as_("note_fallback"),
            lambda metrics: metrics.note.coalesce(param("x"), param("y")).as_(
                "coalesced"
            ),
            lambda metrics: metrics.note.nullif(param("zz")).as_("nullif_note"),
        )
        .query()
    )

    row = con.execute(q, p).fetchone()
    assert tuple(row) == (10.75, -10.8, "n/a", "x", None)


def test_extended_aggregate_functions_run_on_sqlite() -> None:
    con = _conn()
    con.executescript("""
        CREATE TABLE payments (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            amount INTEGER,
            category TEXT NOT NULL
        );
        """)
    con.executemany(
        "INSERT INTO payments (id, user_id, amount, category) VALUES (?, ?, ?, ?)",
        [
            (1, 10, 2000, "A"),
            (2, 10, 2500, "A"),
            (3, 10, 3000, "B"),
            (4, 20, 1500, "A"),
            (5, 20, None, "B"),
        ],
    )

    q, p = (
        table("payments")
        .group_by("user_id")
        .select(
            "user_id",
            lambda payments: payments.amount.sum().as_("sum_amount"),
            lambda payments: payments.amount.min().as_("min_amount"),
            lambda payments: payments.amount.max().as_("max_amount"),
            lambda payments: payments.amount.total().as_("total_amount"),
            lambda payments: payments.category.group_concat(param("|")).as_(
                "categories"
            ),
        )
        .query()
    )

    rows = con.execute(q, p).fetchall()
    assert [tuple(r) for r in rows] == [
        (10, 7500, 2000, 3000, 7500.0, "A|A|B"),
        (20, 1500, 1500, 1500, 1500.0, "A|B"),
    ]
