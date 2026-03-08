# Google Keep アクセスガイド

Google Keep へのアクセスは `keep-cli.py` ([gkeepapi](https://github.com/kiwiz/gkeepapi) ラッパー) で行う。

> **注意**: gkeepapi は非公式 API を使用しており、Google の変更で動作しなくなる可能性がある。

## インストール

```bash
pip3 install --user gkeepapi
```

## セットアップ

### 1. Google アプリパスワードの取得

1. Google アカウントで 2 段階認証を有効化
2. [アプリパスワード](https://myaccount.google.com/apppasswords) ページでパスワードを生成
3. 生成されたパスワードを控える

### 2. マスタートークンの取得

```bash
pip3 install --user gpsoauth
python3 -c "
from gpsoauth import perform_master_login
email = input('Email: ')
password = input('App Password: ')
result = perform_master_login(email, password)
token = result.get('Token')
if token:
    print(f'Master token: {token}')
else:
    print(f'Error: {result}')
"
```

### 3. 設定ファイルに記述

`~/.config/agent-tools/config.json` の `keep` セクションに記述:

```json
{
  "keep": {
    "email": "<your_email>",
    "master_token": "<master_token>"
  }
}
```

## CLI ツール

```bash
~/keep-cli.py list                                   # ノート一覧
~/keep-cli.py list --pinned                           # ピン留めのみ
~/keep-cli.py list --limit 50                         # 件数指定
~/keep-cli.py read <note_id>                          # ノート読み取り
~/keep-cli.py search <query>                          # テキスト検索
~/keep-cli.py create "タイトル" "本文"                 # テキストノート作成
~/keep-cli.py create-list "タイトル" "項目1, 項目2"    # チェックリスト作成
```

## 制約

- 非公式 API のため予告なく動作しなくなる可能性がある
- リマインダー、画像、手書きメモは非対応
- 初回同期は全ノートを取得するため遅い（状態は `~/.config/agent-tools/keep-state.json` にキャッシュ）
- マスタートークンは広範なアカウントアクセス権を持つため厳重に管理すること
