"""
献立自動提案アルゴリズム
"""
import random as _random
from typing import Optional


def _get_ingredient_names(recipe: dict) -> set[str]:
    """レシピの食材名セットを返す"""
    return {ing["name"] for ing in recipe.get("ingredients", [])}


def _score_recipe(
    recipe: dict,
    must_ingredients: list[str],
    prioritize_favorites: bool,
    consider_nutrition: bool = True,
) -> float:
    """
    レシピのスコアを計算する。
    - マスト食材1品ごとに +10
    - お気に入り優先モードでfavoriteなら +5
    - consider_nutrition=True のとき妊婦向け栄養ボーナス：鉄>=2.0→+3、葉酸>=50→+2、カルシウム>=80→+2
    """
    score = 0.0
    ingredient_names = {ing["name"] for ing in recipe.get("ingredients", [])}

    for must in must_ingredients:
        must_lower = must.lower().strip()
        for ing_name in ingredient_names:
            if must_lower in ing_name.lower():
                score += 10
                break

    if prioritize_favorites and recipe.get("favorite", False):
        score += 5

    if consider_nutrition:
        n = recipe.get("nutrition_per_serving", {})
        if n.get("iron_mg", 0) >= 2.0:
            score += 3
        if n.get("folate_ug", 0) >= 50:
            score += 2
        if n.get("calcium_mg", 0) >= 80:
            score += 2

    return score


def _check_ingredient_overlap(
    selected: list[dict],
    candidate: dict,
    threshold: int = 3,
) -> bool:
    """
    既選択レシピと候補の食材が threshold 個以上共通するなら True を返す。
    調味料カテゴリは除外（醤油・みりんは全レシピ共通なので意味がない）。
    """
    exclude_categories = {"調味料", "その他"}
    candidate_ings = {
        ing["name"]
        for ing in candidate.get("ingredients", [])
        if ing.get("category") not in exclude_categories
    }
    for sel in selected:
        sel_ings = {
            ing["name"]
            for ing in sel.get("ingredients", [])
            if ing.get("category") not in exclude_categories
        }
        overlap = len(candidate_ings & sel_ings)
        if overlap >= threshold:
            return True
    return False


def _calc_total_cook_time(recipes: list[dict]) -> int:
    """レシピリストの準備+調理時間の合計を返す"""
    return sum(r.get("prep_time_min", 0) + r.get("cook_time_min", 0) for r in recipes)


def suggest_recipes(
    all_recipes: list[dict],
    main_count: int,
    side_count: int,
    soup_count: int,
    must_ingredients: list[str],
    prioritize_favorites: bool,
    random_seed: Optional[int] = None,
    pressure_count: int = 0,
    microwave_main_count: int = 0,
    microwave_side_count: int = 0,
    consider_nutrition: bool = True,
    time_limit_enabled: bool = True,
    time_limit_min: int = 120,
    allow_ingredient_overlap: bool = False,
) -> dict:
    """
    献立を自動提案する。

    通常枠とレンジ枠はcookerフィルタで独立しているため、カウントは別々に設定する。
    電気圧力鍋は並行調理のため調理時間チェックから除外される。

    Returns:
        {"main": [...], "side": [...], "soup": [...], "pressure": [...],
         "microwave_main": [...], "microwave_side": [...]}
    """
    rng = _random.Random(random_seed)

    # 特殊調理器具（通常プールから除外）
    SPECIAL_COOKERS = {"electric_pressure", "microwave"}

    # 通常枠とレンジ枠・圧力鍋枠はcookerフィルタで分離。カウントは独立。
    CATEGORY_MAP = [
        ("main",           "主菜",   main_count,           "normal"),
        ("side",           "副菜",   side_count,           "normal"),
        ("soup",           "スープ", soup_count,           "normal"),
        ("pressure",       "主菜",   pressure_count,       "electric_pressure"),
        ("microwave_main", "主菜",   microwave_main_count, "microwave"),
        ("microwave_side", "副菜",   microwave_side_count, "microwave"),
    ]

    result: dict[str, list[dict]] = {
        "main": [], "side": [], "soup": [], "pressure": [],
        "microwave_main": [], "microwave_side": [],
    }

    # 全カテゴリを横断して選定済みレシピを追跡（調理時間のグローバル計算用）
    all_selected: list[dict] = []

    for cat_key, cat_jp, count, cooker_filter in CATEGORY_MAP:
        if count <= 0:
            continue

        if cooker_filter == "normal":
            pool = [r for r in all_recipes
                    if r["category"] == cat_jp and r.get("cooker", "normal") not in SPECIAL_COOKERS]
        else:
            pool = [r for r in all_recipes
                    if r["category"] == cat_jp and r.get("cooker") == cooker_filter]
        if not pool:
            continue

        # プールをシャッフルして毎回異なる選定順序にする
        rng.shuffle(pool)

        # スコアリング：マスト食材・お気に入り・栄養のいずれかが有効な場合のみ実施
        use_scoring = bool(must_ingredients) or prioritize_favorites or consider_nutrition
        if use_scoring:
            scored = [
                (r, _score_recipe(r, must_ingredients, prioritize_favorites, consider_nutrition)
                 + rng.random() * 2)
                for r in pool
            ]
            scored.sort(key=lambda x: x[1], reverse=True)
        else:
            # 完全ランダム（シャッフル済みプールをそのまま使用）
            scored = [(r, 0.0) for r in pool]

        selected: list[dict] = []

        # Phase 1: マスト食材含むレシピを優先して確保
        must_matches = [r for r, s in scored if s >= 10]
        for r in must_matches:
            if len(selected) >= count:
                break
            selected.append(r)
            all_selected.append(r)

        # Phase 2: 残枠を制約チェックしながら充填
        already_ids = {r["id"] for r in selected}
        for r, _ in scored:
            if len(selected) >= count:
                break
            if r["id"] in already_ids:
                continue
            # 調理時間チェック（電気圧力鍋は並行調理なので除外）
            if time_limit_enabled and cat_key not in ("pressure",):
                r_time = r.get("prep_time_min", 0) + r.get("cook_time_min", 0)
                if _calc_total_cook_time(all_selected) + r_time > time_limit_min:
                    continue
            # 食材重複チェック
            if not allow_ingredient_overlap and _check_ingredient_overlap(selected, r, threshold=3):
                continue
            selected.append(r)
            all_selected.append(r)
            already_ids.add(r["id"])

        # Phase 3: フォールバック（制約を無視して残枠を必ず埋める）
        if len(selected) < count:
            already_ids = {r["id"] for r in selected}
            for r, _ in scored:
                if len(selected) >= count:
                    break
                if r["id"] in already_ids:
                    continue
                selected.append(r)
                already_ids.add(r["id"])

        result[cat_key] = selected[:count]

    return result
