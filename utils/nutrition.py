# 栄養計算ユーティリティ
# 妊婦後期・4歳児・成人男性の推奨値と充足率を計算する

# --- 推奨値定数 ---

# 妊婦後期 1日の目標量
PREGNANCY_DAILY = {
    "calories": 2350,    # kcal
    "protein_g": 75,     # g
    "iron_mg": 21.0,     # mg
    "calcium_mg": 650,   # mg
    "folate_ug": 640,    # μg
    "salt_g": 6.5,       # g (上限)
}

# 4歳児 1日の目標量
CHILD_DAILY = {
    "calories": 1300,    # kcal
    "protein_g": 20,     # g
    "iron_mg": 5.5,      # mg
    "calcium_mg": 550,   # mg
    "folate_ug": 200,    # μg
    "salt_g": 3.5,       # g (上限)
}

# 成人男性（夫）1日の目標量（30代・身体活動レベル中）
HUSBAND_DAILY = {
    "calories": 2650,    # kcal
    "protein_g": 65,     # g
    "iron_mg": 7.5,      # mg
    "calcium_mg": 800,   # mg
    "folate_ug": 240,    # μg
    "salt_g": 7.5,       # g (上限)
}

# 夕食の割合（1日の35%）
DINNER_RATIO = 0.35

# 栄養素キー一覧
NUTRITION_KEYS = ["calories", "protein_g", "fat_g", "carbs_g", "salt_g", "iron_mg", "calcium_mg", "folate_ug"]


def get_pregnancy_dinner_targets() -> dict:
    """妊婦後期の夕食分推奨値を返す"""
    return {k: v * DINNER_RATIO for k, v in PREGNANCY_DAILY.items()}


def get_child_dinner_targets() -> dict:
    """4歳児の夕食分推奨値を返す"""
    return {k: v * DINNER_RATIO for k, v in CHILD_DAILY.items()}


def get_husband_dinner_targets() -> dict:
    """成人男性（夫）の夕食分推奨値を返す"""
    return {k: v * DINNER_RATIO for k, v in HUSBAND_DAILY.items()}


def calc_nutrition_total(recipe_ids: list[str], recipes: list[dict]) -> dict:
    """選択されたレシピIDリストから3人前合計の栄養素を計算する"""
    recipe_map = {r["id"]: r for r in recipes}

    total = {k: 0.0 for k in NUTRITION_KEYS}

    for rid in recipe_ids:
        recipe = recipe_map.get(rid)
        if recipe is None:
            continue
        n = recipe.get("nutrition_per_serving", {})
        servings = recipe.get("servings", 3)
        ratio = 3 / servings if servings else 1
        for key in total:
            total[key] += n.get(key, 0) * ratio

    return total


def calc_nutrition_per_person(recipe_ids: list[str], recipes: list[dict]) -> dict:
    """1人前の栄養素合計を計算する"""
    total = calc_nutrition_total(recipe_ids, recipes)
    return {k: v / 3 for k, v in total.items()}


def calc_nutrition_from_grams(recipe_id: str, amount_g: float, recipes: list[dict]) -> dict:
    """
    指定レシピを amount_g グラム食べた場合の栄養素を計算する。
    serving_size_adult_g を橋渡しにして100gあたりの密度を求め、amount_g にスケーリングする。
    """
    recipe = next((r for r in recipes if r["id"] == recipe_id), None)
    if recipe is None or amount_g <= 0:
        return {k: 0.0 for k in NUTRITION_KEYS}

    n = recipe.get("nutrition_per_serving", {})
    ref_g = recipe.get("serving_size_adult_g", 80)
    if ref_g <= 0:
        ref_g = 80

    result = {}
    for key in NUTRITION_KEYS:
        per_100g = n.get(key, 0) / ref_g * 100
        result[key] = per_100g * amount_g / 100

    return result


def calc_nutrition_from_staple(staple: dict, amount_g: float) -> dict:
    """主食アイテムの栄養素を gram ベースで計算する"""
    if amount_g <= 0:
        return {k: 0.0 for k in NUTRITION_KEYS}
    per_100g = staple.get("nutrition_per_100g", {})
    return {key: per_100g.get(key, 0) * amount_g / 100 for key in NUTRITION_KEYS}


def calc_nutrition_from_ready_made(item: dict, amount_g: float) -> dict:
    """既製品の栄養素を gram ベースで計算する"""
    if amount_g <= 0:
        return {k: 0.0 for k in NUTRITION_KEYS}
    per_100g = item.get("nutrition_per_100g", {})
    return {key: per_100g.get(key, 0) * amount_g / 100 for key in NUTRITION_KEYS}


def sum_nutrition(*nutrition_dicts: dict) -> dict:
    """複数の栄養素辞書を合算して返す"""
    result = {k: 0.0 for k in NUTRITION_KEYS}
    for d in nutrition_dicts:
        for key in NUTRITION_KEYS:
            result[key] += d.get(key, 0)
    return result


def calc_sufficiency(nutrition: dict, targets: dict) -> dict:
    """各栄養素の充足率を計算する（0.0〜上限なし）"""
    result = {}
    for key, target in targets.items():
        if target <= 0:
            result[key] = 0.0
        else:
            result[key] = nutrition.get(key, 0) / target
    return result


def get_nutrient_label(key: str) -> str:
    """栄養素キーを日本語ラベルに変換する"""
    labels = {
        "calories": "カロリー",
        "protein_g": "タンパク質",
        "fat_g": "脂質",
        "carbs_g": "炭水化物",
        "salt_g": "塩分",
        "iron_mg": "鉄",
        "calcium_mg": "カルシウム",
        "folate_ug": "葉酸",
    }
    return labels.get(key, key)


def get_nutrient_unit(key: str) -> str:
    """栄養素キーの単位を返す"""
    units = {
        "calories": "kcal",
        "protein_g": "g",
        "fat_g": "g",
        "carbs_g": "g",
        "salt_g": "g",
        "iron_mg": "mg",
        "calcium_mg": "mg",
        "folate_ug": "μg",
    }
    return units.get(key, "")


def is_upper_limit(key: str) -> bool:
    """塩分のように上限値として扱う栄養素かどうか"""
    return key == "salt_g"
