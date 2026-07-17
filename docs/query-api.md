# クエリ API

## エントリポイント

- table(name)
- table(name, as_=alias)

返されるオブジェクトは、mixin により次のチェインをサポートします:

- where
- order
- range
- group_by
- select
- exists

## where

```python
table("users").where(lambda users: users.age >= 20)
```

lambda には、引数名に対応したテーブルオブジェクトが渡されます。

callback 本文は Python AST として解析されるため、`and` / `or` や比較の連鎖をそのまま書けます。

## コールバック評価タイミング

コールバック（lambda/関数）は、すべてクエリ構築時に評価されます。

- where: where 呼び出し時に評価されます。
- select/order/group_by/having: 各メソッド呼び出し時に評価されます。
- join の on: inner_join/left_join/right_join/full_join の各呼び出し時に評価されます。
- cross_join には on コールバックがありません。

そのため、同じクエリオブジェクトに対して query を複数回呼んでも、コールバックは再評価されません。

## order

```python
.order(("age", "asc"), (lambda users: users.created_at + 1, "desc"))
```

- Direction は asc または desc
- 複数テーブル文脈では、order に文字列カラムは使えません。

## range

```python
.range(offset=0, limit=10)
```

注意: limit が None の場合、LIMIT/OFFSET 句は出力されません。

## select

```python
.select("name", lambda users: users.name.upper().as_("upper_name"), distinct=True)
```

- 文字列カラム名の自動修飾は単一テーブル文脈でのみ有効です。
- 複数テーブル文脈では lambda + table.column 形式を使ってください。

## group_by と having

```python
from sq5l import asterisk

.group_by(
    "user_id",
    having=lambda payments: (asterisk.count() >= 3) & (payments.amount.avg() >= 2000),
)
```

## サブクエリ関連

### in_

```python
.where(lambda users: users.id.in_(
    table("orders").where(lambda orders: orders.total >= 3000).select(lambda orders: orders.user_id)
))
```

### exists

```python
.where(lambda u: table("orders", as_="o")
    .where(lambda o: (o.user_id == u.id) & (o.total >= 3000))
    .exists()
)
```

exists で明示的な select がない場合、レンダラは SELECT 1 を出力します。

## JOIN

- inner_join(other, on=...)
- left_join(other, on=...)
- right_join(other, on=...)
- full_join(other, on=...)
- cross_join(other)

cross_join は ON 句を取りません。

注意:

- left_join と cross_join は sqlite3 実行で検証済みです。
- right_join と full_join は SQL 生成を提供しますが、実行可否は利用する DB 方言に依存します。

## 派生テーブルの別名

```python
sub = (
    table("orders", as_="o")
    .group_by(lambda o: o.user_id)
    .select(lambda o: o.user_id)
    .as_("t")
)

q, p = sub.where(lambda t: t.user_id >= 1).select(lambda t: t.user_id).query()
```
