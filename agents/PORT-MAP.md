# エージェントツール ポート割り当て表

各 CDP ベースのツールが使う VNC ディスプレイ / VNC ポート / CDP ポートの一覧。
すべてデフォルト値。環境変数で上書き可能。

| ツール         | VNC Display | VNC Port | CDP Port | noVNC (Web) | URL                            |
|----------------|-------------|----------|----------|-------------|--------------------------------|
| Keep           | :1          | 5901     | 9221     | 6081        | https://keep.google.com        |
| Teams          | :2          | 5902     | 9222     | 6082        | https://teams.microsoft.com    |
| Slack          | :3          | 5903     | 9223     | 6083        | https://app.slack.com          |
| MoneyForward   | :4          | 5904     | 9224     | 6084        | https://moneyforward.com       |
| Notion         | :5          | 5905     | 9225     | 6085        | https://www.notion.so          |

### pfr-mics-tools (`:1X` 番台)

| ツール         | VNC Display | VNC Port | CDP Port | noVNC (Web) | URL                            |
|----------------|-------------|----------|----------|-------------|--------------------------------|
| Concur         | :11         | 5911     | 9231     | 6091        | https://www.concursolutions.com|

### noVNC ポータル

```bash
~/novnc-start.sh            # 全ディスプレイの noVNC プロキシを起動
~/novnc-start.sh status     # 状態確認
~/novnc-start.sh stop       # 全停止
```

ポータルページ: http://localhost:6080/portal.html
（個別アクセス: http://localhost:{noVNC Port}）

## 環境変数での上書き例

```bash
# Keep を別ポートで起動
KEEP_CDP_PORT=9321 KEEP_VNC_DISPLAY=:11 KEEP_VNC_PORT=5911 ~/keep-start.sh
KEEP_CDP_URL=http://localhost:9321 python3 ~/keep-cli.py list

# Teams を別ポートで起動
TEAMS_CDP_PORT=9322 TEAMS_VNC_DISPLAY=:12 TEAMS_VNC_PORT=5912 ~/teams-start.sh
TEAMS_CDP_URL=http://localhost:9322 python3 ~/teams-cli.py chats
```

## 採番ルール

### dotfiles_public/agents（個人ツール: `:1`〜`:9`）

- VNC Display: `:1` から連番
- VNC Port: `5900 + Display番号`
- CDP Port: `9220 + Display番号`
- noVNC (Web): `6080 + Display番号`
- 次の空き: `:6` / `5906` / `9226` / `6086`

### pfr-mics-tools（社内ツール: `:11`〜`:19`）

- VNC Display: `:11` から連番
- VNC Port: `5900 + Display番号`
- CDP Port: `9220 + Display番号`
- noVNC (Web): `6080 + Display番号`
- 次の空き: `:12` / `5912` / `9232` / `6092`
