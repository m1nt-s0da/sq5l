# クイックスタート

## 1. 基本的な SELECT

```python
from sq5l import table, param

q, p = (
    table("users")
    .where(
        lambda users: (
            users.name.like(param("Mic%")) and users.age >= param(30)
        ) or users.deleted_at == None
    )
    .order(("created_at", "desc"))
    .select("id", "name")
    .query()
)

# q: SQL 文字列
# p: パラメータタプル
```

## 2. JOIN クエリ

```python
from sq5l import table, param

q, p = (
    table("users", as_="u")
    .inner_join(table("orders", as_="o"), on=lambda u, o: o.user_id == u.id)
    .where(lambda o: o.total >= param(3000))
    .select(lambda u: u.id, lambda u: u.name, lambda o: o.id.as_("order_id"))
    .query()
)
```

JOIN は以下をサポートします。

- inner_join(other, on=...)
- left_join(other, on=...)
- right_join(other, on=...)
- full_join(other, on=...)
- cross_join(other)

```python
# CROSS JOIN 例
q, p = (
    table("a", as_="a")
    .cross_join(table("b", as_="b"))
    .select(lambda a: a.id, lambda b: b.id)
    .query()
)
```

注意: right_join / full_join の実行可否は DB 方言依存です。

## 3. 派生テーブルの別名

```python
from sq5l import table, asterisk, param

q, p = (
    table("orders", as_="o")
    .group_by(lambda o: o.user_id)
    .select(lambda o: o.user_id, lambda: asterisk.count().as_("order_count"))
    .as_("t")
    .where(lambda t: t.order_count >= param(3))
    .select(lambda t: t.user_id, lambda t: t.order_count)
    .query()
)
```

## 4. INSERT と UPDATE

```python
from sq5l import table, param

# 値を使った INSERT
q1, p1 = table("users").insert({"name": "Mike", "age": 15}).query()

# where 付き UPDATE
q2, p2 = (
    table("users")
    .where(lambda users: users.id == param(10))
    .update({"name": "Michael"})
    .query()
)
```
