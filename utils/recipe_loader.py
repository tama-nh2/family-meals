import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
RECIPES_FILE = DATA_DIR / "recipes.json"
WEEKLY_PLAN_FILE = DATA_DIR / "weekly_plan.json"

NUTRITION_MASTER_FILE = DATA_DIR / "nutrition_master.json"

DEFAULT_PLAN = {
    "settings": {
        "main_count": 4,
        "side_count": 4,
        "soup_count": 1,
        "pressure_count": 0,
    },
    "selected_recipes": {
        "main": [],
        "side": [],
        "soup": [],
        "pressure": [],
    },
}


def load_recipes() -> list[dict]:
    with open(RECIPES_FILE, encoding="utf-8") as f:
        recipes = json.load(f)
    # IDの重複を排除（JSONに不正なエントリが混入した場合の防御）
    seen: set[str] = set()
    unique = []
    for r in recipes:
        if r["id"] not in seen:
            seen.add(r["id"])
            unique.append(r)
    return unique


def get_recipe_by_id(recipe_id: str, recipes: list[dict] | None = None) -> dict | None:
    if recipes is None:
        recipes = load_recipes()
    for r in recipes:
        if r["id"] == recipe_id:
            return r
    return None


def get_recipes_by_category(category: str, recipes: list[dict] | None = None) -> list[dict]:
    if recipes is None:
        recipes = load_recipes()
    if category == "すべて":
        return recipes
    return [r for r in recipes if r["category"] == category]


def load_weekly_plan() -> dict:
    if not WEEKLY_PLAN_FILE.exists():
        return DEFAULT_PLAN.copy()
    try:
        with open(WEEKLY_PLAN_FILE, encoding="utf-8") as f:
            plan = json.load(f)
        # 欠損キーをデフォルト値で補完
        plan.setdefault("settings", DEFAULT_PLAN["settings"].copy())
        plan.setdefault("selected_recipes", DEFAULT_PLAN["selected_recipes"].copy())
        plan["settings"].setdefault("main_count", 4)
        plan["settings"].setdefault("side_count", 4)
        plan["settings"].setdefault("soup_count", 1)
        plan["settings"].setdefault("pressure_count", 0)
        plan["selected_recipes"].setdefault("main", [])
        plan["selected_recipes"].setdefault("side", [])
        plan["selected_recipes"].setdefault("soup", [])
        plan["selected_recipes"].setdefault("pressure", [])
        return plan
    except (json.JSONDecodeError, KeyError):
        return DEFAULT_PLAN.copy()


def save_weekly_plan(plan: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(WEEKLY_PLAN_FILE, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)


def save_recipes(recipes: list[dict]) -> None:
    """レシピリストをファイルに書き戻す（お気に入りトグル用）"""
    with open(RECIPES_FILE, "w", encoding="utf-8") as f:
        json.dump(recipes, f, ensure_ascii=False, indent=2)


def toggle_favorite(recipe_id: str) -> list[dict]:
    """指定IDのレシピの favorite フラグを反転して保存し、更新済みリストを返す"""
    recipes = load_recipes()
    for r in recipes:
        if r["id"] == recipe_id:
            r["favorite"] = not r.get("favorite", False)
            break
    save_recipes(recipes)
    return recipes


def add_recipe(recipe: dict) -> list[dict]:
    """新しいレシピを追加して保存し、更新済みリストを返す"""
    recipes = load_recipes()
    recipes.append(recipe)
    save_recipes(recipes)
    return recipes


def load_nutrition_master() -> list[dict]:
    """食材栄養マスタを読み込む"""
    if not NUTRITION_MASTER_FILE.exists():
        return []
    with open(NUTRITION_MASTER_FILE, encoding="utf-8") as f:
        return json.load(f)


def estimate_recipe_nutrition(
    ingredients: list[dict],
    servings: int,
    nutrition_master: list[dict] | None = None,
) -> dict:
    """
    食材リストとサービング数から 1 人前の栄養素を推定する。
    nutrition_master がない食材は 0 として扱う。
    """
    if nutrition_master is None:
        nutrition_master = load_nutrition_master()

    master_map = {m["name"]: m["nutrition_per_100g"] for m in nutrition_master}
    keys = ["calories", "protein_g", "fat_g", "carbs_g", "salt_g", "iron_mg", "calcium_mg", "folate_ug"]
    total = {k: 0.0 for k in keys}

    for ing in ingredients:
        name = ing.get("name", "")
        amount_g = ing.get("amount_g", 0)
        ndata = master_map.get(name)
        if ndata:
            for k in keys:
                total[k] += ndata.get(k, 0.0) * amount_g / 100.0

    if servings <= 0:
        return total
    return {k: round(v / servings, 1) for k, v in total.items()}
