# Google Keep アクセスガイド

Google Keep へのアクセスは `keep-cli.py` (`gkeepapi` / Google Keep API ラッパー) で行う。
Chrome CDP は使わない。

## 前提

```bash
pip3 install --user --break-system-packages gkeepapi gpsoauth
```

## セットアップ

```bash
# 1. 初回または token 切れ時に再認証
~/keep-cli.py auth your_email@gmail.com

# 2. 以後は保存済み token を利用
~/keep-cli.py list
```

必要なら環境変数で上書きできる。

```bash
KEEP_EMAIL=your_email@gmail.com \
KEEP_MASTER_TOKEN=YOUR_MASTER_TOKEN \
python3 ~/keep-cli.py list
```

## CLI ツール

```bash
~/keep-cli.py auth your_email@gmail.com              # master_token を再取得して保存
~/keep-cli.py list                                   # ノート一覧
~/keep-cli.py list --limit 50                        # 件数指定
~/keep-cli.py search <query>                         # Keep 内検索
~/keep-cli.py open "<query>"                         # ノートを開いて読む
~/keep-cli.py read                                   # 直前に開いたノートを読む
~/keep-cli.py read "<query>"                         # 指定ノートを読む
~/keep-cli.py create "タイトル" "本文"                # テキストノート作成
~/keep-cli.py archive "<query>"                      # ノートをアーカイブ
~/keep-cli.py dump "<query>"                         # ノート JSON (debug)
```

## 制約

- `auth` では Google アカウントのパスワード入力が必要
- `master_token` の再取得可否は Google 側の認証ポリシーに依存する
- 現状はテキストノート中心。画像、リマインダー、ラベル編集は未対応
- Google Keep の非公式 API ラッパー依存のため、サーバー側変更で追従が必要になる場合がある
