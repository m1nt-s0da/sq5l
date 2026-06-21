# sq5l ドキュメント

sq5l は、SQL 文字列とパラメータタプルを生成する軽量な SQL ビルダです。

主な公開 API:

- table
- param
- asterisk

## ドキュメント一覧

- [クイックスタート](quickstart.md)
- [クエリ API](query-api.md)
- [書き込み API](write-api.md)
- [ルールと制約](rules-and-limitations.md)

## 設計の要点

- 式は AST（式木）として構築されます。
- SQL 文字列は AST からレンダリングされます。
- 値は None 比較を除いて param でラップして使います。
- lambda は位置ではなく、引数名（キーワード）で解決されます。

## 補足

- JOIN は inner/left/right/full/cross をサポートします。
- right/full は SQL 生成を提供し、実行可否は利用 DB 方言に依存します。
