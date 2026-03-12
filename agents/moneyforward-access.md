# Money Forward CLI

`moneyforward-cli.py` は Chrome CDP 経由で Money Forward の画面を読み、口座一覧や取引っぽい行を抽出したり、自然言語で質問したりするための CLI です。

## 初回セットアップ

1. `~/moneyforward-start.sh` を実行
2. VNC で `localhost:5902` に接続
3. Chrome 上で Money Forward にログイン
4. ログイン後、別ターミナルで `~/moneyforward-cli.py status` を実行

## よく使うコマンド

- `~/moneyforward-cli.py status`
- `~/moneyforward-cli.py snapshot`
- `~/moneyforward-cli.py accounts`
- `~/moneyforward-cli.py transactions --limit 30`
- `~/moneyforward-cli.py ask "今月の大きい支出を教えて"`

## ask コマンド

`ask` は `OPENAI_API_KEY` が必要です。

```bash
export OPENAI_API_KEY=...
~/moneyforward-cli.py ask "最新の見えている資産状況を要約して"
```

## 注意

- 公開 API ではなく画面抽出なので、Money Forward の DOM 変更で壊れる可能性があります。
- 取得対象は「現在ブラウザに表示されている情報」が中心です。必要なページを開いてから `snapshot` / `ask` を使ってください。
