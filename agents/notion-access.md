# Notion access

guest 権限のまま Notion を CLI から操作するための Chrome CDP ベースの手順。

## 概要

- 公式 API ではなく、ログイン済み Chrome を DevTools Protocol 経由で操作する
- 読み取り: ページ一覧、現在ページ本文、ページ遷移
- 書き込み: 末尾への段落追記、テキストを含む段落の削除

利用ツール:

- `~/notion-start.sh`
- `~/notion-browser-cli.py`

## 前提

以下が入っていること:

```bash
sudo apt install google-chrome-stable
pip3 install --user --break-system-packages websockets
```

既存の X display が必要。現在の既定値は `:2`。

## 起動

```bash
~/notion-start.sh
```

既定では以下を使う:

- display: `:2`
- CDP port: `9226`
- Chrome profile: `~/.config/agent-tools/chrome-notion`

環境変数で上書き可能:

```bash
NOTION_DISPLAY=:2
NOTION_CDP_PORT=9226
NOTION_CHROME_DATA_DIR=~/.config/agent-tools/chrome-notion
```

## ログイン

VNC などで該当 display 上の Chrome を開き、Notion に一度ログインする。  
ログイン後は Chrome プロファイルに状態が保持される。

## コマンド例

状態確認:

```bash
python3 ~/notion-browser-cli.py status
python3 ~/notion-browser-cli.py title
```

ページ一覧:

```bash
python3 ~/notion-browser-cli.py pages --limit 20
```

ページを開く:

```bash
python3 ~/notion-browser-cli.py open-page "Physical AI社内研究"
```

本文を読む:

```bash
python3 ~/notion-browser-cli.py read
```

末尾に新しい段落を追記:

```bash
python3 ~/notion-browser-cli.py append "CLI から追記"
```

末尾に新しい heading を追記:

```bash
python3 ~/notion-browser-cli.py append-heading 1 "要件整理"
python3 ~/notion-browser-cli.py append-heading 2 "未完タスク"
```

テキストを含む段落を削除:

```bash
python3 ~/notion-browser-cli.py delete-block "CLI から追記"
```

## 注意

- DOM 構造に依存するため、Notion UI 変更で壊れる
- `delete-block` は最短一致の段落を消すので、曖昧な文字列は避ける
- 公式 API 版の `~/notion-cli.py` は integration token 前提で、guest 権限では通常使えない
