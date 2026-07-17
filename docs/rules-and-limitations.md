# ルールと制約

## 式のルール

- CanBeValue は CanBeValue 同士でのみ演算できます。
- None 比較のみ特別扱いです:
  - value == None => IS NULL
  - value != None => IS NOT NULL
- None 以外の生値はそのまま渡すと自動で SQL パラメータ化されます。

## 別名ルール

- as は Python 予約語のため、as_ を使います。
- value.as_(...) で得られる AliasedValue は、select の lambda 戻り値でのみ有効です。

## lambda の名前解決

- lambda は、利用可能なテーブル参照に対して引数名で解決されます。
- 必須引数名が現在の文脈に存在しない場合は TypeError になります。
- そのため、クエリ文脈での別名と lambda 引数名は一致させる必要があります。

## lambda の評価タイミング

- where の lambda は where 呼び出し時に評価されます。
- select/order/group_by/having/join(on) の lambda は各メソッド呼び出し時に評価されます。
- update 系の value lambda / pair lambda も update 呼び出し時に評価されます。
- cross_join、insert、update のマッピング形式には callback がありません。
- いずれも query 呼び出し時には再評価されません。

## callback の構文

- where などの callback は Python AST として解析されます。
- `and` / `or` と比較の連鎖をそのまま使えます。

## 文字列カラムのショートカット

- select/group_by/order での文字列カラム指定は単一テーブル文脈でのみ使えます。
- 複数テーブル文脈では lambda + table.column を使ってください。

## SQL 出力上の注意

- 括弧は保守的に付与されるため、過剰な括弧が出る場合があります。
- exists で select を明示しない場合は SELECT 1 を出力します。
- range は limit がある場合にのみ LIMIT/OFFSET を出力します。
- insert の ignore は現在 INSERT IGNORE として出力されます（INSERT OR IGNORE ではありません）。

## 現在使える JOIN

- inner_join
- left_join
- right_join
- full_join
- cross_join

補足:

- right_join / full_join の実行可否は利用する DB 方言に依存します。

## 現在の公開 API

- table
- asterisk
