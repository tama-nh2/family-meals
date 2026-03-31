"""
食事記録の I/O とグラムベースの栄養計算
"""
import json
from datetime import date
from pathlib import Path

from utils.nutrition import (
    calc_nutrition_from_grams,
    calc_nutrition_from_staple,
    calc_nutrition_from_ready_made,
    sum_nutrition,
    NUTRITION_KEYS,
)

DATA_DIR = Path(__file__).parent.parent / "data"
DAILY_LOG_FILE = DATA_DIR / "daily_log.json"
STAPLE_FOODS_FILE = DATA_DIR / "staple_foods.json"
READY_MADE_FILE = DATA_DIR / "ready_made.json"


# --- 主食・既製品マスタ ---

def load_staple_foods() -> list[dict]:
    with open(STAPLE_FOODS_FILE, encoding="utf-8") as f:
        return json.load(f)


def load_ready_made() -> list[dict]:
    with open(READY_MADE_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_ready_made(items: list[dict]) -> None:
    """既製品マスタを上書き保存する（管理UI用）"""
    with open(READY_MADE_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


# --- 日別食事記録 ---

def load_daily_log() -> dict:
    """daily_log.json を読み込む。ファイルが存在しない場合は {} を返す。"""
    if not DAILY_LOG_FILE.exists():
        return {}
    try:
        with open(DAILY_LOG_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_daily_log(log: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(DAILY_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


def build_empty_person_log() -> dict:
    """空の person_log スケルトンを返す"""
    return {
        "recipe_items": [],
        "staple_items": [],
        "ready_made_items": [],
    }


def get_today_log(log: dict, meal_type: str = "dinner") -> dict:
    """
    今日の date キーのログを取得する。
    存在しない場合は空スケルトンを返す（ファイルには書かない）。
    """
    today_str = date.today().isoformat()
    day_log = log.get(today_str, {})
    meal_log = day_log.get(meal_type, {})
    return {
        "husband": meal_log.get("husband", build_empty_person_log()),
        "wife": meal_log.get("wife", build_empty_person_log()),
        "child": meal_log.get("child", build_empty_person_log()),
    }


def calc_person_nutrition(
    person_log: dict,
    recipes: list[dict],
    staple_foods: list[dict],
    ready_made_items: list[dict],
) -> dict:
    """
    1人分の食事ログから合計栄養素を計算して返す。
    """
    staple_map = {s["id"]: s for s in staple_foods}
    ready_map = {i["id"]: i for i in ready_made_items}

    parts = []

    # 作り置きレシピ
    for item in person_log.get("recipe_items", []):
        parts.append(
            calc_nutrition_from_grams(item["recipe_id"], item["amount_g"], recipes)
        )

    # 主食
    for item in person_log.get("staple_items", []):
        staple = staple_map.get(item["staple_id"])
        if staple:
            parts.append(calc_nutrition_from_staple(staple, item["amount_g"]))

    # 既製品
    for item in person_log.get("ready_made_items", []):
        ready = ready_map.get(item["ready_made_id"])
        if ready:
            parts.append(calc_nutrition_from_ready_made(ready, item["amount_g"]))

    if not parts:
        return {k: 0.0 for k in NUTRITION_KEYS}

    return sum_nutrition(*parts)
