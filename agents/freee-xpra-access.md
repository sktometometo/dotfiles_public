# freee xpra アクセスガイド

freee をデスクトップ全体ではなく Chrome ウィンドウ単位でブラウザ共有したい場合は、`xpra` ベースの専用セッションを使う。

## 起動

```bash
~/freee-xpra-start.sh
```

デフォルト設定:

- xpra display: `:14`
- HTML5 client: `http://127.0.0.1:14500/`
- Chrome CDP: `http://localhost:9225`
- Chrome profile: `~/.config/agent-tools/chrome-freee`

起動後の状態は `~/.cache/agent-tools/chrome-sessions/freee-xpra.json` に保存される。

## 特徴

- XPRA セッションには freee 用 Chrome だけを起動する
- Keep / Teams / VNC デスクトップと干渉しない
- Chrome プロファイルは `freee-start.sh` と共有するため、cookie / ログイン状態を持ち越せる
- HTML5 client でブラウザから操作できる

## 接続

同じマシン上のブラウザなら:

```text
http://127.0.0.1:14500/
```

リモートから使うなら SSH トンネルで:

```bash
ssh -L 14500:127.0.0.1:14500 <host>
```

その後、ローカルブラウザで `http://127.0.0.1:14500/` を開く。
