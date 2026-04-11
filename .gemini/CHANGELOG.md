# Changelog

## [2026-04-11]
- 【修正】Streamlit Cloud上でアプリが `ModuleNotFoundError: No module named 'pytz'` エラーによって起動しない問題を解決するため、`requirements.txt` に欠落していた依存パッケージ `pytz` を追加

## [2026-03-19]
- 【追加】旧仕様で署名された契約書が再起動によりダウンロード不可になる（ファイル名がハッシュ由来だったため見失う）問題に対し、不足している「署名証明書」と「スタンプ」を監査DB上の署名ログからその場で動的に再生成・結合するフォールバック機能（`recreate_signed_contract_if_missing`）を実装（`services.py`, `app.py`）
- 署名済みPDFのフッター（全ページ）に電子署名済である旨とハッシュ値（SHA256）、署名日時が印字されるように修正（`utils.py`, `services.py`）
- 日本語フォント（HeiseiKakuGo-W5）を使用して印字するよう `create_stamp_pdf` を修正
- 管理画面および署名完了画面からダウンロードできるファイルが、正しく署名スタンプ・証明書付きの統合版PDFになるように修正（`app.py`、以前は署名後も元PDFがDLされていた問題を解消）
- Supabase連携利用時にも一意なファイル名で参照・ダウンロード可能になるように、アップロード時の挙動とパス解決関数を修正（`utils.py`, `services.py`）

## [2026-03-17]
- `contract_service` プロジェクトへ作業コンテキストを切り替え
- 初期 `STATUS.md` と `CHANGELOG.md` を作成
- ユーザー報告（Supabase停止によるログイン不可）を受け、`test_connection.py` で疎通確認を実施。DBの接続は成功（復旧済み）したが、Storageバケット `contracts` が未検出であることを確認。
