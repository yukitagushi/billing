# Green Permit Intake App (IWATE / Iwaizumi)

スマホ入力 (Next.js) + Excel生成API (FastAPI) の最小構成です。

## 構成

- `/Users/taguchiyuusei/green-permit-intake-app/apps/web`
  - Next.js (TypeScript) PWA 風UI
  - `schema.json` 由来の動的フォーム
  - ローカル保存 + サーバ保存
  - チェック結果表示 + ZIP生成
- `/Users/taguchiyuusei/green-permit-intake-app/services/excel_filler`
  - FastAPI
  - SQLite保存 (`cases`, `case_answers`, `exports`)
  - `mapping.yml` + `schema.json` によるExcel転記
  - `extract_schema.py` (質問票Excel -> schema.json)

## 主要ファイル

- `/Users/taguchiyuusei/green-permit-intake-app/services/excel_filler/templates/001388353.xlsx`
- `/Users/taguchiyuusei/green-permit-intake-app/services/excel_filler/templates/001388356.xls`
- `/Users/taguchiyuusei/green-permit-intake-app/services/excel_filler/templates/iwate_iwaizumi_ai_input_questionnaire.xlsx`
- `/Users/taguchiyuusei/green-permit-intake-app/services/excel_filler/app/schema.json` (601 fields)

## セットアップ

### 1) Excel API (FastAPI)

```bash
cd /Users/taguchiyuusei/green-permit-intake-app/services/excel_filler
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### schema.json 再生成

```bash
cd /Users/taguchiyuusei/green-permit-intake-app/services/excel_filler/scripts
python3 extract_schema.py
```

#### `.xls` -> `.xlsx` 変換（任意）

```bash
cd /Users/taguchiyuusei/green-permit-intake-app/services/excel_filler/scripts
./convert_xls.sh
```

LibreOffice (`soffice`) がある場合、
`001388356_converted.xlsx` を `templates/` に作成します。

#### API起動

```bash
cd /Users/taguchiyuusei/green-permit-intake-app/services/excel_filler
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

### 2) Web (Next.js)

```bash
cd /Users/taguchiyuusei/green-permit-intake-app/apps/web
npm install
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 npm run dev
```

ブラウザで `http://localhost:3000` を開きます。

## テスト

```bash
cd /Users/taguchiyuusei/green-permit-intake-app/services/excel_filler
source .venv/bin/activate
pytest -q
```

`test_mapping_coverage.py` はマッピング不足を warning として扱い、
段階的な拡張を許容します。

## MVPの範囲

- 3ステップ入力（申請者 / 営業所・車両 / 人員・資金・運賃）
- 途中保存（localStorage + SQLite）
- 入力チェック（必須・形式・一部相関）
- Excel転記 + `review_report.xlsx` を含む ZIP生成

## 補足

- `.xls` は直接編集しない設計です。`001388356_converted.xlsx` へ変換後に自動出力対象になります。
- 変換前は ZIP に `.xls` 原本とレビューを同梱し、要対応が分かるようにしています。
