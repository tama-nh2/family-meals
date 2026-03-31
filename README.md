# 🍱 家族ごはん管理アプリ

週次作り置きを中心に、妊婦後期の妻・4歳の子供・夫の3人家族の食事を管理する Streamlit アプリです。

## 機能

| タブ | 内容 |
|------|------|
| 🏠 献立 | 今週の作り置きレシピを選択・管理（電気圧力鍋スロット対応）|
| 📋 レシピ | レシピ一覧・お気に入り・手動追加 |
| 🛒 買い出し | 週次献立から食材を自動集約、チェックリスト |
| 📝 記録 | 今日の夕食（作り置き＋ご飯＋既製品）を記録・栄養計算 |
| 🥗 栄養 | 週次献立の栄養充足率（妻・子供・夫） |
| ✨ 提案 | マスト食材・お気に入り条件で献立を自動提案 |

## ローカルで起動

```bash
git clone <repo-url>
cd family-meals
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Cloud へのデプロイ

1. GitHub にリポジトリを push（`data/daily_log.json` と `data/shopping_list.json` は `.gitignore` で除外済み）
2. [share.streamlit.io](https://share.streamlit.io) でリポジトリを接続
3. Main file: `app.py` を指定して Deploy

> **注意**: Streamlit Cloud はファイルシステムが ephemeral のため、`daily_log.json` や `shopping_list.json` はセッション間で保持されません。永続化が必要な場合は Streamlit Community Cloud の Secrets + 外部 DB（Supabase 等）を使用してください。

## データファイル

| ファイル | 説明 |
|---------|------|
| `data/recipes.json` | レシピマスタ（21品） |
| `data/staple_foods.json` | 主食マスタ（白米・玄米等5品） |
| `data/ready_made.json` | 既製品マスタ（納豆・チーズ等） |
| `data/nutrition_master.json` | 食材別栄養値マスタ（レシピ栄養推定用） |
| `data/weekly_plan.json` | 今週の献立（git 管理） |
| `data/daily_log.json` | 日別食事記録（git 除外） |
| `data/shopping_list.json` | 買い出しチェック状態（git 除外） |

## 栄養目標

- **妻（妊婦後期）**: 鉄 21mg/日、葉酸 640μg/日、カルシウム 650mg/日
- **子供（4歳）**: カルシウム 550mg/日、鉄 5.5mg/日
- **夫**: カロリー 2650kcal/日
- 夕食比率: 1日の35%として計算
