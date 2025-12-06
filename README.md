# 物件検索システム

複数の不動産サイトから物件情報を取得し、データベース化して検索・閲覧できるシステムです。

## セットアップ

1. 必要なライブラリをインストールします。
   ```bash
   pip install -r requirements.txt
   ```

## 使い方

### 1. データの取得 (スクレイピング)
設定されたサイトから最新の物件情報を取得し、データベースに保存します。
```bash
python main.py --scrape
```
> **注意**: `scrapers/suumo_scraper.py` 内の `target_url` を、希望する検索条件のURLに変更してください。

### 2. 保存された物件の表示
データベースに保存された物件一覧を表示します。
```bash
python main.py --show
```

## 構成
- `config.py`: 全体設定
- `db/`: データベース関連
- `scrapers/`: スクレイピングモジュール
    - `suumo_scraper.py`: SUUMO用スクレイパー
