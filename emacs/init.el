;;
;; init.el
;;

;;
;; default coding environment
;;

;;; localization
(set-locale-environment nil)
(set-language-environment 'Japanese)
(set-keyboard-coding-system 'utf-8)
(set-terminal-coding-system 'utf-8)
(set-buffer-file-coding-system 'utf-8)
(setq default-buffer-file-condig-system 'utf-8)
(prefer-coding-system 'utf-8)

;;; 行数を表示
(global-linum-mode t)

;; カーソルを点滅をやめる
(blink-cursor-mode 0)

;; カーソル行のハイライト
(global-hl-line-mode t)

;; 対応する括弧を光らせる
(show-paren-mode 1)

;; ウィンドウ内に収まらないときだけ、カッコ内も光らせる
(setq show-paren-style 'mixed)
;(set-face-background 'show-paren-match-face "gray")
;(set-face-foreground 'show-paren-match-face "black")

;; タブを空白4つにする
(setq-default tab-width 4 indent-tabs-mode nil)

;; 改行コードを表示する
(setq eol-mnemonic-doc "(CRLF)")
(setq eol-mnemonic-mac "(CR)")
(setq eol-mnemonic-unix "(LF)")

;; スペース、タブなどを可視化する
(global-whitespace-mode 1)

;; 行末の空白を表示
(setq-default show-trailing-whitespace t)

;; C-kで行全体を削除する
(setq kill-whole-line t)


;;
;; Color Theme
;;
(load-theme 'adwaita t)

;;
;; definition of new key prefix
;;
(global-set-key "\C-m" 'newline-and-indent)
(global-set-key "\C-j" 'newline)


;;
;; completion
;;
;;; 補完時に大文字小文字を区別しない
(setq completion-ignore-case t)
(setq read-file-name-completion-ignore-case t)

;;
(add-to-list 'load-path (shell-command-to-string "rospack find euslime"))
(if (not (and (string-prefix-p "/opt" (getenv "EUSDIR"))
              (string-prefix-p "/opt" (shell-command-to-string "rospack find euslime"))))
    (setq euslime-compile-path "~/.euslime_source")
  (setq euslime-compile-path "~/.euslime_opt")
)
(require 'euslime-config)
(setq inferior-euslisp-program "roseus")
(slime-setup '(slime-fancy slime-banner slime-repl-ansi-color))
