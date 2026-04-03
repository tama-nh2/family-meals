# CLAUDE.md — family-meals プロジェクト

## プロジェクト概要

家族3人（夫・妻〔妊婦後期〕・4歳息子）の週次作り置きを管理する Streamlit アプリ。
献立選択・買い出しリスト・食事記録・栄養分析・自動提案の6タブ構成。

---

## 家族構成と料理の制約

| 家族 | 状況 | 主な制約 |
|------|------|---------|
| 夫 | 成人男性（30代） | なし |
| 妻 | 妊婦後期 | 辛味 NG・塩分控えめ |
| 息子 | 4歳 | 辛味 NG・柔らかめ |

**料理選定ルール：**
- 辛味 NG（唐辛子・カレー粉強め等は使わない）
- 作り置き向き（冷蔵 3〜5 日保存可能なもの）
- 子供 OK タグ推奨
- 仕込み合計（prep_time_min + cook_time_min）は 2 時間以内

---

## 分量設計

- `batch_servings` の目安: **10 食**
- 大人 1 食: **80 g** / 子供 1 食: **40 g**
- 仕込み量は `batch_servings` を基準に比例スケール

---

## 技術スタック

- **言語 / フレームワーク:** Python 3 + Streamlit ≥ 1.32.0, pandas ≥ 2.0.0
- **データ永続化:** JSON ファイル（`data/` 配下）
- **デプロイ:** Streamlit Community Cloud
- **GitHub:** https://github.com/tama-nh2/family-meals

---

## ディレクトリ構成

```
family-meals/
├── app.py                   # メインアプリ（6タブ）
├── requirements.txt
├── data/
│   ├── recipes.json         # レシピマスタ（Git 管理）
│   ├── nutrition_master.json # 食材栄養データベース
│   ├── ready_made.json      # 既製品リスト
│   ├── staple_foods.json    # 主食リスト（米・パン等）
│   ├── weekly_plan.json     # 週間献立（Git 管理）
│   ├── daily_log.json       # 食事記録（.gitignore）
│   └── shopping_list.json   # 買い出しチェックリスト（.gitignore）
└── utils/
    ├── recipe_loader.py     # レシピ読み書き・重複排除
    ├── nutrition.py         # 栄養計算・推奨値定数
    ├── shopping.py          # 買い物リスト集計
    ├── suggest.py           # 献立自動提案アルゴリズム
    └── meal_recorder.py     # 食事記録の読み書き
```

---

## レシピ JSON スキーマ（`data/recipes.json`）

```json
{
  "id": "recipe_001",
  "name": "鶏の照り焼き",
  "category": "主菜",
  "cooker": "normal",
  "servings": 3,
  "batch_servings": 10,
  "serving_size_adult_g": 80,
  "serving_size_child_g": 40,
  "prep_time_min": 10,
  "cook_time_min": 20,
  "storage_days": 4,
  "ingredients": [
    {
      "name": "鶏もも肉",
      "amount": 450,
      "unit": "g",
      "category": "肉類"
    }
  ],
  "steps": ["手順1", "手順2"],
  "nutrition_per_serving": {
    "calories": 280,
    "protein_g": 25,
    "fat_g": 14,
    "carbs_g": 8,
    "salt_g": 1.5,
    "iron_mg": 1.2,
    "calcium_mg": 15,
    "folate_ug": 12
  },
  "tags": ["作り置き", "子供OK", "定番"],
  "favorite": false
}
```

**フィールド補足:**
- `category`: `"主菜"` / `"副菜"` / `"スープ"`
- `cooker`: `"normal"` / `"electric_pressure"`
- `unit`: `"g"` / `"ml"` / `"大さじ"` / `"個"` / `"少々"` など
- `tags`: 任意の文字列配列。`"作り置き"` `"子供OK"` `"定番"` `"電気圧力鍋"` など

---

## よく使うコマンド

```bash
# アプリ起動（ローカル）
streamlit run app.py

# 変更を push
git add -A && git commit -m "変更内容の説明" && git push
```

---

## 注意事項

| 項目 | 内容 |
|------|------|
| ID 重複禁止 | `recipe_XXX` 形式で連番。既存の最大番号を確認してから採番 |
| amount ≠ 0 | `ingredients[].amount` に 0 を入れると買い出し計算がおかしくなる |
| session_state | ページリロード跨ぎの状態管理に `st.session_state` を使用。変更後は必ず保存関数を呼ぶ |
| デプロイ反映 | Streamlit Community Cloud は push 後 2〜3 分で反映 |

---

## 栄養推奨値

夕食 = 1 日の **35%** として計算（`utils/nutrition.py` の `DINNER_RATIO = 0.35`）。

### 1 日分の目標量

| 対象 | カロリー | タンパク質 | 脂質 | 鉄 | カルシウム | 葉酸 | 塩分（上限） |
|------|---------|-----------|------|-----|----------|------|------------|
| 妻（妊婦後期） | 2350 kcal | 75 g | — | 21.0 mg | 650 mg | 640 μg | 6.5 g |
| 息子（4歳児） | 1300 kcal | 20 g | — | 5.5 mg | 550 mg | 200 μg | 3.5 g |
| 夫（成人男性） | 2650 kcal | 65 g | — | 7.5 mg | 800 mg | 240 μg | 7.5 g |

### 夕食分の目標量（×0.35）

| 対象 | カロリー | タンパク質 | 鉄 | カルシウム | 葉酸 | 塩分（上限） |
|------|---------|-----------|-----|----------|------|------------|
| 妻（妊婦後期） | 822 kcal | 26.3 g | 7.35 mg | 227.5 mg | 224 μg | 2.3 g |
| 息子（4歳児） | 455 kcal | 7.0 g | 1.93 mg | 192.5 mg | 70 μg | 1.2 g |
| 夫（成人男性） | 928 kcal | 22.8 g | 2.63 mg | 280 mg | 84 μg | 2.6 g |
