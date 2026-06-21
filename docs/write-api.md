# 書き込み API

## insert

### 値を使った insert

```python
q, p = table("users").insert({"name": "Mike", "age": 15}).query()
```

### SELECT からの insert

```python
q, p = table("teen_users").insert(
    ("name", "age"),
    table("users").where(lambda users: users.age < param(20)).select("name", "age"),
).query()
```

### ignore モード

```python
q, p = table("users").insert({"name": "Mike", "age": 15}, ignore=True).query()
```

現在のレンダラは INSERT IGNORE を出力します。

## update

update は where の後で利用できます。join チェインでも where を経由して利用できます。

### マッピング形式

```python
q, p = (
    table("users")
    .where(lambda users: users.id == param(10))
    .update({"name": "Michael"})
    .query()
)
```

### 単一カラム形式

```python
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
```

### ペア lambda 形式

```python
q, p = (
    table("users")
    .inner_join("batch", on=lambda users, batch: users.id == batch.user_id)
    .where(lambda users: users.gender == param("male"))
    .update(
        lambda users, batch: (users.name, batch.name),
        lambda users, batch: (users.age, batch.age + param(1)),
    )
    .query()
)
```

この形式は SQLite 向けの UPDATE ... SET ... FROM ... WHERE ... を生成します。
（ON 句を持つ join の条件は WHERE に統合されます）

join は inner_join / left_join / right_join / full_join / cross_join が使えます。
ただし right_join / full_join の実行可否は DB 方言依存です。

## コールバック評価タイミング

- insert には callback はありません。
- where の条件 lambda は、where 呼び出し時に評価されます。
- update("col", lambda ...) や update(lambda ...: (left, right)) の lambda は、update 呼び出し時に評価されます。

そのため、同じ更新クエリオブジェクトで query を複数回呼んでも、update 側の lambda は再評価されません。
