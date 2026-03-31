"""
買い出しリスト生成・管理
"""
import json
from datetime import date
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
SHOPPING_LIST_FILE = DATA_DIR / "shopping_list.json"

CATEGORY_ORDER = ["肉・魚", "野菜", "大豆・豆腐", "海藻・乾物", "卵・乳", "調味料", "その他"]


def _week_key() -> str:
    """ISO 週キーを返す（例: '2026-W14'）"""
    return date.today().strftime("%G-W%V")


def load_shopping_state() -> dict[str, bool]:
    """
    今週の買い出しチェック状態を返す。
    週が変わっていたら空 dict を返す（週次リセット）。
    """
    if not SHOPPING_LIST_FILE.exists():
        return {}
    try:
        with open(SHOPPING_LIST_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}
    return data.get(_week_key(), {})


def save_shopping_state(checked: dict[str, bool]) -> None:
    """今週の買い出しチェック状態を保存する"""
    try:
        with open(SHOPPING_LIST_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError, FileNotFoundError):
        data = {}
    data[_week_key()] = checked
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(SHOPPING_LIST_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def aggregate_ingredients(selected_recipes: dict, all_recipes: list[dict]) -> dict[str, dict]:
    """
    週次献立のレシピIDリストから食材を集約する。

    Returns:
        {
            "食材名": {
                "category": "野菜",
                "amount_g": 300.0,
                "unit": "g",
                "recipes": ["レシピ名A", "レシピ名B"],
            },
            ...
        }
    """
    recipe_map = {r["id"]: r for r in all_recipes}
    aggregated: dict[str, dict] = {}

    all_ids = []
    for ids in selected_recipes.values():
        all_ids.extend(ids)

    for recipe_id in all_ids:
        recipe = recipe_map.get(recipe_id)
        if not recipe:
            continue
        batch = recipe.get("batch_servings", 1)
        for ing in recipe.get("ingredients", []):
            name = ing["name"]
            category = ing.get("category", "その他")
            # amount_g（手動追加レシピ）または amount（既存レシピ）を参照
            amount = ing.get("amount_g", ing.get("amount", 0))
            total_g = amount * batch

            if name in aggregated:
                aggregated[name]["amount_g"] += total_g
                if recipe["name"] not in aggregated[name]["recipes"]:
                    aggregated[name]["recipes"].append(recipe["name"])
            else:
                aggregated[name] = {
                    "category": category,
                    "amount_g": total_g,
                    "unit": ing.get("unit", "g"),
                    "recipes": [recipe["name"]],
                }

    return aggregated


def group_by_category(ingredients: dict[str, dict]) -> dict[str, list[tuple[str, dict]]]:
    """
    食材辞書をカテゴリ別にグループ化する。

    Returns:
        OrderedDict-like: {category: [(name, info), ...]}
    """
    grouped: dict[str, list] = {cat: [] for cat in CATEGORY_ORDER}

    for name, info in ingredients.items():
        cat = info.get("category", "その他")
        if cat not in grouped:
            grouped[cat] = []
        grouped[cat].append((name, info))

    # 空カテゴリを除去
    return {cat: items for cat, items in grouped.items() if items}


def format_amount(info: dict) -> str:
    """食材の量を表示用文字列に整形する"""
    amount_g = info.get("amount_g", 0)
    unit = info.get("unit", "g")
    if unit == "g":
        if amount_g >= 1000:
            return f"{amount_g / 1000:.1f}kg"
        return f"{int(amount_g)}g"
    return f"{amount_g}{unit}"


def build_clipboard_text(
    grouped: dict[str, list[tuple[str, dict]]],
    checked: dict[str, bool],
) -> str:
    """買い出しリストをクリップボード用テキストに整形する"""
    lines = ["【買い出しリスト】"]
    for category, items in grouped.items():
        lines.append(f"\n■ {category}")
        for name, info in items:
            done = "✓" if checked.get(name, False) else "□"
            amount = format_amount(info)
            lines.append(f"  {done} {name}（{amount}）")
    return "\n".join(lines)
