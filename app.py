import random
from datetime import date

import pandas as pd
import streamlit as st

from utils.meal_recorder import (
    build_empty_person_log,
    calc_person_nutrition,
    get_today_log,
    load_daily_log,
    load_ready_made,
    load_staple_foods,
    save_daily_log,
    save_ready_made,
)
from utils.nutrition import (
    CHILD_DAILY,
    DINNER_RATIO,
    HUSBAND_DAILY,
    PREGNANCY_DAILY,
    calc_nutrition_per_person,
    get_child_dinner_targets,
    get_husband_dinner_targets,
    get_nutrient_label,
    get_nutrient_unit,
    get_pregnancy_dinner_targets,
    is_upper_limit,
)
from utils.recipe_loader import (
    add_recipe as add_recipe_to_file,
    estimate_recipe_nutrition,
    get_recipe_by_id,
    get_recipes_by_category,
    load_nutrition_master,
    load_recipes,
    load_weekly_plan,
    save_recipes,
    save_weekly_plan,
    toggle_favorite,
)
from utils.shopping import (
    aggregate_ingredients,
    build_clipboard_text,
    format_amount,
    group_by_category,
    load_shopping_state,
    save_shopping_state,
)
from utils.suggest import suggest_recipes

st.set_page_config(
    page_title="🍱 家族ごはん管理",
    page_icon="🍱",
    layout="centered",
)

# --- CSS ---
st.markdown(
    """
    <style>
    .recipe-card {
        background: #f8f9fa;
        border-radius: 12px;
        padding: 12px 16px;
        margin-bottom: 8px;
        border-left: 4px solid #4CAF50;
    }
    .recipe-card-pressure {
        background: #fff8e1;
        border-radius: 12px;
        padding: 12px 16px;
        margin-bottom: 8px;
        border-left: 4px solid #FF9800;
    }
    .recipe-card-name { font-size: 1.05rem; font-weight: bold; margin-bottom: 4px; }
    .recipe-card-meta { font-size: 0.82rem; color: #666; }
    .slot-empty {
        background: #f0f2f6;
        border-radius: 12px;
        padding: 12px 16px;
        margin-bottom: 8px;
        border: 2px dashed #ccc;
        text-align: center;
        color: #888;
    }
    .section-header { font-size: 1.15rem; font-weight: bold; margin-top: 1rem; margin-bottom: 0.5rem; }
    .shop-item { padding: 4px 0; font-size: 0.95rem; }
    @media (max-width: 640px) {
        .recipe-card-name { font-size: 1rem; }
        .recipe-card-meta { font-size: 0.78rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- データ初期化 ---
@st.cache_data
def get_recipes():
    return load_recipes()


@st.cache_data
def get_staple_foods():
    return load_staple_foods()


@st.cache_data
def get_nutrition_master():
    return load_nutrition_master()


if "weekly_plan" not in st.session_state:
    st.session_state.weekly_plan = load_weekly_plan()

recipes = get_recipes()


# --- ヘルパー関数 ---
def get_all_selected_ids() -> list[str]:
    plan = st.session_state.weekly_plan
    ids = []
    for key in ["main", "side", "soup", "pressure"]:
        ids.extend(plan["selected_recipes"].get(key, []))
    return ids


def save_plan():
    save_weekly_plan(st.session_state.weekly_plan)


def add_recipe_to_plan(category_key: str, recipe_id: str):
    st.session_state.weekly_plan["selected_recipes"][category_key].append(recipe_id)
    save_plan()


def remove_recipe_from_plan(category_key: str, idx: int):
    st.session_state.weekly_plan["selected_recipes"][category_key].pop(idx)
    save_plan()


def replace_recipe_in_plan(category_key: str, idx: int, recipe_id: str):
    st.session_state.weekly_plan["selected_recipes"][category_key][idx] = recipe_id
    save_plan()


def do_toggle_favorite(recipe_id: str):
    toggle_favorite(recipe_id)
    get_recipes.clear()
    st.rerun()


CATEGORY_CONFIG = {
    "main":     {"label": "🍖 主菜",   "emoji": "🍖", "key": "main",     "cat_jp": "主菜"},
    "side":     {"label": "🥗 副菜",   "emoji": "🥗", "key": "side",     "cat_jp": "副菜"},
    "soup":     {"label": "🍲 スープ", "emoji": "🍲", "key": "soup",     "cat_jp": "スープ"},
    "pressure": {"label": "⚡ 圧力鍋", "emoji": "⚡", "key": "pressure", "cat_jp": "主菜"},
}

CAT_EMOJI = {"主菜": "🍖", "副菜": "🥗", "スープ": "🍲"}


def render_recipe_slots(category_key: str, count: int, show_fav_button: bool = True):
    """指定カテゴリのレシピスロットを表示する"""
    cfg = CATEGORY_CONFIG[category_key]
    selected = st.session_state.weekly_plan["selected_recipes"].get(category_key, [])
    cat_jp = cfg["cat_jp"]

    # pressure は electric_pressure のみ、それ以外はnormal
    if category_key == "pressure":
        available = [r for r in recipes if r["category"] == cat_jp and r.get("cooker") == "electric_pressure"]
    else:
        available = [r for r in recipes if r["category"] == cat_jp and r.get("cooker", "normal") != "electric_pressure"]

    st.markdown(f"<div class='section-header'>{cfg['label']}</div>", unsafe_allow_html=True)

    card_class = "recipe-card-pressure" if category_key == "pressure" else "recipe-card"

    for i in range(count):
        if i < len(selected):
            recipe = get_recipe_by_id(selected[i], recipes)
            if recipe:
                star = "★" if recipe.get("favorite") else "☆"
                col1, col_star, col2, col3 = st.columns([4, 1, 1, 1])
                with col1:
                    st.markdown(
                        f"<div class='{card_class}'>"
                        f"<div class='recipe-card-name'>{cfg['emoji']} {recipe['name']}</div>"
                        f"<div class='recipe-card-meta'>⏱ {recipe['prep_time_min'] + recipe['cook_time_min']}分 &nbsp;|&nbsp; 🗓 {recipe['storage_days']}日保存</div>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                with col_star:
                    if show_fav_button and st.button(star, key=f"plan_fav_{category_key}_{i}", help="お気に入り"):
                        do_toggle_favorite(recipe["id"])
                with col2:
                    if st.button("変更", key=f"change_{category_key}_{i}"):
                        st.session_state[f"changing_{category_key}_{i}"] = True
                with col3:
                    if st.button("削除", key=f"del_{category_key}_{i}"):
                        remove_recipe_from_plan(category_key, i)
                        st.rerun()

                if st.session_state.get(f"changing_{category_key}_{i}"):
                    options = [r["name"] for r in available if r["id"] != selected[i]]
                    id_map = {r["name"]: r["id"] for r in available}
                    chosen_name = st.selectbox(
                        "レシピを選んでください",
                        options,
                        key=f"sel_{category_key}_{i}",
                    )
                    col_ok, col_cancel = st.columns(2)
                    with col_ok:
                        if st.button("決定", key=f"ok_{category_key}_{i}"):
                            replace_recipe_in_plan(category_key, i, id_map[chosen_name])
                            st.session_state[f"changing_{category_key}_{i}"] = False
                            st.rerun()
                    with col_cancel:
                        if st.button("キャンセル", key=f"cancel_{category_key}_{i}"):
                            st.session_state[f"changing_{category_key}_{i}"] = False
                            st.rerun()
        else:
            st.markdown(
                f"<div class='slot-empty'>＋ スロット {i + 1} が空です</div>",
                unsafe_allow_html=True,
            )
            selected_set = set(selected)
            options = [r["name"] for r in available if r["id"] not in selected_set]
            if options:
                col_sel, col_add = st.columns([4, 1])
                with col_sel:
                    chosen_name = st.selectbox(
                        "レシピを選ぶ",
                        ["（選択してください）"] + options,
                        key=f"add_sel_{category_key}_{i}",
                        label_visibility="collapsed",
                    )
                with col_add:
                    if st.button("追加", key=f"add_btn_{category_key}_{i}"):
                        if chosen_name != "（選択してください）":
                            id_map = {r["name"]: r["id"] for r in available}
                            add_recipe_to_plan(category_key, id_map[chosen_name])
                            st.rerun()
            else:
                st.caption("追加できるレシピがありません")


def render_nutrition_bars(title: str, targets: dict, per_person: dict, _daily: dict):
    """栄養プログレスバーセクションを描画する"""
    st.markdown(f"**{title}**")
    display_keys = ["calories", "iron_mg", "calcium_mg", "folate_ug", "salt_g", "protein_g"]
    for key in display_keys:
        if key not in targets:
            continue
        label = get_nutrient_label(key)
        unit = get_nutrient_unit(key)
        target = targets[key]
        value = per_person.get(key, 0)
        ratio = value / target if target > 0 else 0
        bar_val = min(ratio, 1.0)
        st.markdown(
            f"<span style='font-size:0.9rem'>{label}：{value:.1f} {unit} / 目標 {target:.1f} {unit} ({ratio*100:.0f}%)</span>",
            unsafe_allow_html=True,
        )
        st.progress(bar_val)


# ========== タブ ==========
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🏠 献立",
    "📋 レシピ",
    "🛒 買い出し",
    "📝 記録",
    "🥗 栄養",
    "✨ 提案",
])


# ========== Tab 1: 今週の献立 ==========
with tab1:
    st.title("🏠 今週の献立")

    with st.expander("⚙️ 今週の品数設定", expanded=False):
        plan = st.session_state.weekly_plan
        settings = plan["settings"]

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            main_count = st.slider("🍖 主菜", 1, 6, settings["main_count"], key="slider_main")
        with c2:
            side_count = st.slider("🥗 副菜", 1, 6, settings["side_count"], key="slider_side")
        with c3:
            soup_count = st.slider("🍲 スープ", 0, 2, settings["soup_count"], key="slider_soup")
        with c4:
            pressure_count = st.slider("⚡ 圧力鍋", 0, 3, settings.get("pressure_count", 0), key="slider_pressure")

        changed = (
            main_count != settings["main_count"]
            or side_count != settings["side_count"]
            or soup_count != settings["soup_count"]
            or pressure_count != settings.get("pressure_count", 0)
        )
        if changed:
            sel = st.session_state.weekly_plan["selected_recipes"]
            sel["main"] = sel["main"][:main_count]
            sel["side"] = sel["side"][:side_count]
            sel["soup"] = sel["soup"][:soup_count]
            sel.setdefault("pressure", [])
            sel["pressure"] = sel["pressure"][:pressure_count]
            st.session_state.weekly_plan["settings"]["main_count"] = main_count
            st.session_state.weekly_plan["settings"]["side_count"] = side_count
            st.session_state.weekly_plan["settings"]["soup_count"] = soup_count
            st.session_state.weekly_plan["settings"]["pressure_count"] = pressure_count
            save_plan()
            st.rerun()

    plan = st.session_state.weekly_plan

    # --- リセットボタン ---
    if st.button("🗑️ 今週の献立をリセット", key="reset_weekly_plan"):
        st.session_state["confirm_reset_plan"] = True

    if st.session_state.get("confirm_reset_plan", False):
        st.warning("本当にリセットしますか？選択中のレシピが全て削除されます。")
        col_yes, col_no = st.columns(2)
        with col_yes:
            if st.button("✅ リセットする", key="reset_plan_yes"):
                for key in ["main", "side", "soup", "pressure"]:
                    st.session_state.weekly_plan["selected_recipes"][key] = []
                save_plan()
                st.session_state.pop("confirm_reset_plan", None)
                st.success("献立がリセットされました。")
                st.rerun()
        with col_no:
            if st.button("キャンセル", key="reset_plan_no"):
                st.session_state.pop("confirm_reset_plan", None)
                st.rerun()

    render_recipe_slots("main", plan["settings"]["main_count"])
    render_recipe_slots("side", plan["settings"]["side_count"])
    if plan["settings"]["soup_count"] > 0:
        render_recipe_slots("soup", plan["settings"]["soup_count"])
    if plan["settings"].get("pressure_count", 0) > 0:
        render_recipe_slots("pressure", plan["settings"]["pressure_count"])

    st.divider()
    st.markdown("### 🥗 今週の栄養サマリー（1人前 / 夕食）")

    all_ids = get_all_selected_ids()
    if not all_ids:
        st.info("レシピを選ぶと栄養サマリーが表示されます。")
    else:
        per_person = calc_nutrition_per_person(all_ids, recipes)
        col_w, col_c = st.columns(2)
        with col_w:
            render_nutrition_bars("🤰 妻（妊婦後期）", get_pregnancy_dinner_targets(), per_person, PREGNANCY_DAILY)
        with col_c:
            render_nutrition_bars("👦 子供（4歳）", get_child_dinner_targets(), per_person, CHILD_DAILY)


# ========== Tab 2: レシピ一覧 ==========
with tab2:
    st.title("📋 レシピ一覧")

    col_cat, col_fav = st.columns([3, 2])
    with col_cat:
        category_filter = st.radio(
            "カテゴリ",
            ["すべて", "主菜", "副菜", "スープ"],
            horizontal=True,
            key="cat_filter",
        )
    with col_fav:
        show_fav_only = st.checkbox("★ お気に入りのみ", key="fav_only")

    serving_mode = st.radio(
        "表示人数",
        ["3人前", "1人前"],
        horizontal=True,
        key="serving_mode",
    )
    serving_ratio = 1 / 3 if serving_mode == "1人前" else 1.0

    filtered = get_recipes_by_category(category_filter, recipes)
    if show_fav_only:
        filtered = [r for r in filtered if r.get("favorite")]

    if not filtered:
        st.info("該当するレシピがありません。")

    for recipe in filtered:
        cat_emoji = CAT_EMOJI.get(recipe["category"], "🍽")
        cooker_icon = "⚡" if recipe.get("cooker") == "electric_pressure" else ""
        star = "★" if recipe.get("favorite") else "☆"
        rid = recipe["id"]
        with st.expander(f"{cat_emoji}{cooker_icon} {star} {recipe['name']}　⏱{recipe['prep_time_min'] + recipe['cook_time_min']}分　🗓{recipe['storage_days']}日"):

            # --- アクションボタン行 ---
            col_info, col_fav_btn, col_edit_btn, col_del_btn = st.columns([4, 1, 1, 1])
            with col_info:
                st.markdown(f"**カテゴリ:** {recipe['category']}　|　**保存:** 冷蔵{recipe['storage_days']}日")
            with col_fav_btn:
                fav_label = "★ 解除" if recipe.get("favorite") else "☆ 登録"
                if st.button(fav_label, key=f"list_fav_{rid}"):
                    do_toggle_favorite(rid)
            with col_edit_btn:
                if st.button("✏️", key=f"edit_{rid}", help="編集"):
                    st.session_state[f"editing_{rid}"] = not st.session_state.get(f"editing_{rid}", False)
                    st.session_state.pop(f"confirm_delete_{rid}", None)
                    st.rerun()
            with col_del_btn:
                if st.button("🗑️", key=f"delete_{rid}", help="削除"):
                    st.session_state[f"confirm_delete_{rid}"] = True
                    st.session_state.pop(f"editing_{rid}", None)
                    st.rerun()

            # --- 削除確認 ---
            if st.session_state.get(f"confirm_delete_{rid}", False):
                st.warning(f"「{recipe['name']}」を削除しますか？この操作は元に戻せません。")
                col_yes, col_no = st.columns(2)
                with col_yes:
                    if st.button("✅ 削除する", key=f"delete_yes_{rid}"):
                        updated = [r for r in get_recipes() if r["id"] != rid]
                        save_recipes(updated)
                        get_recipes.clear()
                        st.session_state.pop(f"confirm_delete_{rid}", None)
                        st.rerun()
                with col_no:
                    if st.button("キャンセル", key=f"delete_no_{rid}"):
                        st.session_state.pop(f"confirm_delete_{rid}", None)
                        st.rerun()

            # --- 編集フォーム ---
            elif st.session_state.get(f"editing_{rid}", False):
                st.divider()
                st.markdown("#### ✏️ レシピを編集")

                ed_name = st.text_input("レシピ名", value=recipe["name"], key=f"ed_{rid}_name")
                ed_cat_col, ed_cook_col = st.columns(2)
                with ed_cat_col:
                    cat_options = ["主菜", "副菜", "スープ"]
                    ed_category = st.selectbox("カテゴリ", cat_options,
                        index=cat_options.index(recipe["category"]) if recipe["category"] in cat_options else 0,
                        key=f"ed_{rid}_cat")
                with ed_cook_col:
                    cook_options = ["normal（通常）", "electric_pressure（電気圧力鍋）"]
                    cur_cook_idx = 1 if recipe.get("cooker") == "electric_pressure" else 0
                    ed_cooker = st.selectbox("調理器具", cook_options, index=cur_cook_idx, key=f"ed_{rid}_cooker")
                ed_cooker_val = "electric_pressure" if "electric_pressure" in ed_cooker else "normal"

                et1, et2, et3 = st.columns(3)
                with et1:
                    ed_prep = st.number_input("準備時間(分)", 0, 60, recipe["prep_time_min"], key=f"ed_{rid}_prep")
                with et2:
                    ed_cook_t = st.number_input("調理時間(分)", 0, 120, recipe["cook_time_min"], key=f"ed_{rid}_cook")
                with et3:
                    ed_storage = st.number_input("保存日数", 1, 7, recipe["storage_days"], key=f"ed_{rid}_storage")

                es1, es2, es3 = st.columns(3)
                with es1:
                    ed_servings = st.number_input("サービング数", 1, 20, recipe.get("servings", 3), key=f"ed_{rid}_serv")
                with es2:
                    ed_adult_g = st.number_input("大人1食(g)", 10, 300, recipe.get("serving_size_adult_g", 80), key=f"ed_{rid}_adult")
                with es3:
                    ed_child_g = st.number_input("子供1食(g)", 10, 200, recipe.get("serving_size_child_g", 40), key=f"ed_{rid}_child")

                ings_default = "\n".join(
                    f"{ing['name']},{ing.get('amount', ing.get('amount_g', 0))},{ing.get('category', 'その他')}"
                    for ing in recipe.get("ingredients", [])
                )
                ed_ings_text = st.text_area("食材（食材名,量,カテゴリ）", value=ings_default, height=150, key=f"ed_{rid}_ings")

                steps_default = "\n".join(recipe.get("steps", []))
                ed_steps_text = st.text_area("調理手順", value=steps_default, height=100, key=f"ed_{rid}_steps")

                tags_default = ", ".join(recipe.get("tags", []))
                ed_tags_text = st.text_input("タグ（カンマ区切り）", value=tags_default, key=f"ed_{rid}_tags")

                col_ed_save, col_ed_cancel = st.columns(2)
                with col_ed_save:
                    if st.button("💾 保存", key=f"ed_{rid}_save"):
                        ings_parsed = []
                        for line in ed_ings_text.strip().splitlines():
                            parts = [p.strip() for p in line.split(",")]
                            if len(parts) >= 2:
                                try:
                                    ings_parsed.append({
                                        "name": parts[0],
                                        "amount": float(parts[1]),
                                        "amount_g": float(parts[1]),
                                        "unit": "g",
                                        "category": parts[2] if len(parts) >= 3 else "その他",
                                    })
                                except ValueError:
                                    pass
                        steps_parsed = [s.strip() for s in ed_steps_text.strip().splitlines() if s.strip()]
                        tags_parsed = [t.strip() for t in ed_tags_text.split(",") if t.strip()]
                        updated_recipe = {
                            **recipe,
                            "name": ed_name.strip(),
                            "category": ed_category,
                            "cooker": ed_cooker_val,
                            "servings": int(ed_servings),
                            "batch_servings": int(ed_servings),
                            "serving_size_adult_g": int(ed_adult_g),
                            "serving_size_child_g": int(ed_child_g),
                            "prep_time_min": int(ed_prep),
                            "cook_time_min": int(ed_cook_t),
                            "storage_days": int(ed_storage),
                            "ingredients": ings_parsed if ings_parsed else recipe.get("ingredients", []),
                            "steps": steps_parsed,
                            "tags": tags_parsed,
                        }
                        all_recipes = get_recipes()
                        updated_list = [updated_recipe if r["id"] == rid else r for r in all_recipes]
                        save_recipes(updated_list)
                        get_recipes.clear()
                        st.session_state.pop(f"editing_{rid}", None)
                        st.success(f"「{ed_name.strip()}」を更新しました。")
                        st.rerun()
                with col_ed_cancel:
                    if st.button("キャンセル", key=f"ed_{rid}_cancel"):
                        st.session_state.pop(f"editing_{rid}", None)
                        st.rerun()

            # --- 通常表示 ---
            else:
                st.markdown(f"**材料（{'1人前' if serving_mode == '1人前' else '3人前'}）**")
                ing_data = []
                for ing in recipe["ingredients"]:
                    amount = ing.get("amount", ing.get("amount_g", 0))
                    unit = ing["unit"]
                    if unit in ("g", "ml") and serving_mode == "1人前":
                        display_amount = f"{amount / 3:.0f}"
                    elif unit in ("大さじ", "小さじ", "少々") and serving_mode == "1人前":
                        display_amount = f"{amount / 3:.1f}"
                    else:
                        display_amount = str(amount)
                    ing_data.append({"食材": ing["name"], "量": f"{display_amount} {unit}", "分類": ing.get("category", "")})
                if ing_data:
                    st.dataframe(pd.DataFrame(ing_data), hide_index=True, use_container_width=True)

                st.markdown("**調理手順**")
                for j, step in enumerate(recipe["steps"], 1):
                    st.markdown(f"{j}. {step}")

                st.markdown("**栄養成分**")
                n = recipe["nutrition_per_serving"]
                pregnancy_dinner = get_pregnancy_dinner_targets()
                child_dinner = get_child_dinner_targets()
                nutr_keys = ["calories", "protein_g", "fat_g", "carbs_g", "salt_g", "iron_mg", "calcium_mg", "folate_ug"]
                nutr_rows = []
                for key in nutr_keys:
                    val = n.get(key, 0) * serving_ratio
                    nutr_rows.append({
                        "栄養素": f"{get_nutrient_label(key)}（{get_nutrient_unit(key)}）",
                        "この料理": f"{val:.1f}",
                        "妻目標(夕食)": f"{pregnancy_dinner.get(key, 0):.1f}",
                        "子供目標(夕食)": f"{child_dinner.get(key, 0):.1f}",
                    })
                st.dataframe(pd.DataFrame(nutr_rows), hide_index=True, use_container_width=True)

                tags = " ".join([f"`{t}`" for t in recipe.get("tags", [])])
                st.markdown(f"**タグ:** {tags}")

    # --- 新しいレシピを手動追加 ---
    st.divider()
    with st.expander("➕ 新しいレシピを追加"):
        st.markdown("#### 基本情報")
        nr_name = st.text_input("レシピ名", key="nr_name")
        nr_cat_col, nr_cook_col = st.columns(2)
        with nr_cat_col:
            nr_category = st.selectbox("カテゴリ", ["主菜", "副菜", "スープ"], key="nr_category")
        with nr_cook_col:
            nr_cooker = st.selectbox("調理器具", ["normal（通常）", "electric_pressure（電気圧力鍋）"], key="nr_cooker")
        nr_cooker_val = "electric_pressure" if "electric_pressure" in nr_cooker else "normal"

        time_col1, time_col2, time_col3 = st.columns(3)
        with time_col1:
            nr_prep = st.number_input("準備時間(分)", 0, 60, 10, key="nr_prep")
        with time_col2:
            nr_cook = st.number_input("調理時間(分)", 0, 120, 20, key="nr_cook")
        with time_col3:
            nr_storage = st.number_input("保存日数", 1, 7, 4, key="nr_storage")

        serv_col1, serv_col2, serv_col3 = st.columns(3)
        with serv_col1:
            nr_servings = st.number_input("通常サービング数", 1, 20, 3, key="nr_servings")
        with serv_col2:
            nr_adult_g = st.number_input("大人1食(g)", 10, 300, 80, key="nr_adult_g")
        with serv_col3:
            nr_child_g = st.number_input("子供1食(g)", 10, 200, 40, key="nr_child_g")

        st.markdown("#### 食材（1行1品：食材名,量g,カテゴリ）")
        st.caption("例: 鶏もも肉,300,肉・魚")
        nr_ings_text = st.text_area("食材リスト", height=150, key="nr_ings_text",
                                     placeholder="鶏もも肉,300,肉・魚\n玉ねぎ,100,野菜\n醤油,30,調味料")

        st.markdown("#### 調理手順（1行1ステップ）")
        nr_steps_text = st.text_area("手順", height=100, key="nr_steps_text",
                                      placeholder="鶏肉を一口大に切る。\nフライパンで炒める。")

        nr_tags_text = st.text_input("タグ（カンマ区切り）", key="nr_tags_text", placeholder="鶏肉,簡単,冷凍可")

        # 栄養自動推定
        col_est, col_save = st.columns(2)
        with col_est:
            if st.button("🔢 栄養を自動推定", key="nr_estimate_btn"):
                ings_parsed = []
                for line in nr_ings_text.strip().splitlines():
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 2:
                        try:
                            ings_parsed.append({
                                "name": parts[0],
                                "amount_g": float(parts[1]),
                                "category": parts[2] if len(parts) >= 3 else "その他",
                            })
                        except ValueError:
                            pass
                if ings_parsed:
                    nm = get_nutrition_master()
                    est = estimate_recipe_nutrition(ings_parsed, int(nr_servings), nm)
                    st.session_state["nr_estimated"] = est
                    st.success("推定完了！")
                else:
                    st.warning("食材を入力してください。")

        estimated = st.session_state.get("nr_estimated")
        if estimated:
            st.markdown("**推定栄養成分（1人前）**")
            ks = ["calories", "protein_g", "fat_g", "carbs_g", "salt_g", "iron_mg", "calcium_mg", "folate_ug"]
            e_rows = [{"栄養素": f"{get_nutrient_label(k)}（{get_nutrient_unit(k)}）", "推定値": f"{estimated.get(k, 0):.1f}"} for k in ks]
            st.dataframe(pd.DataFrame(e_rows), hide_index=True, use_container_width=True)

        with col_save:
            if st.button("💾 レシピを保存", key="nr_save_btn"):
                if not nr_name.strip():
                    st.warning("レシピ名を入力してください。")
                else:
                    ings_parsed = []
                    for line in nr_ings_text.strip().splitlines():
                        parts = [p.strip() for p in line.split(",")]
                        if len(parts) >= 2:
                            try:
                                ings_parsed.append({
                                    "name": parts[0],
                                    "amount": float(parts[1]),
                                    "amount_g": float(parts[1]),
                                    "unit": "g",
                                    "category": parts[2] if len(parts) >= 3 else "その他",
                                })
                            except ValueError:
                                pass

                    steps_parsed = [s.strip() for s in nr_steps_text.strip().splitlines() if s.strip()]
                    tags_parsed = [t.strip() for t in nr_tags_text.split(",") if t.strip()]

                    # 栄養推定（未推定なら実行）
                    if estimated:
                        nutrition = estimated
                    else:
                        nm = get_nutrition_master()
                        nutrition = estimate_recipe_nutrition(ings_parsed, int(nr_servings), nm)

                    existing = get_recipes()
                    new_id = f"recipe_{len(existing) + 1:03d}"
                    new_recipe = {
                        "id": new_id,
                        "name": nr_name.strip(),
                        "category": nr_category,
                        "cooker": nr_cooker_val,
                        "servings": int(nr_servings),
                        "batch_servings": int(nr_servings),
                        "serving_size_adult_g": int(nr_adult_g),
                        "serving_size_child_g": int(nr_child_g),
                        "prep_time_min": int(nr_prep),
                        "cook_time_min": int(nr_cook),
                        "storage_days": int(nr_storage),
                        "ingredients": ings_parsed,
                        "steps": steps_parsed,
                        "nutrition_per_serving": nutrition,
                        "tags": tags_parsed,
                        "favorite": False,
                    }
                    add_recipe_to_file(new_recipe)
                    get_recipes.clear()
                    st.session_state.pop("nr_estimated", None)
                    st.success(f"「{nr_name.strip()}」を追加しました！")
                    st.rerun()


# ========== Tab 3: 買い出しリスト ==========
with tab3:
    st.title("🛒 買い出しリスト")

    all_ids_shop = get_all_selected_ids()
    if not all_ids_shop:
        st.info("「献立」タブでレシピを選ぶと、買い出しリストが生成されます。")
    else:
        # 食材集約
        selected_recipes_map = st.session_state.weekly_plan["selected_recipes"]
        aggregated = aggregate_ingredients(selected_recipes_map, recipes)
        grouped = group_by_category(aggregated)

        # 保存済みチェック状態を読み込む
        if "shop_checked" not in st.session_state:
            st.session_state["shop_checked"] = load_shopping_state()

        checked = st.session_state["shop_checked"]

        st.caption(f"📅 今週の献立から {len(aggregated)} 品を集約しました")

        # 特売品入力（提案タブに連携）
        sale_input = st.text_input(
            "🏷️ 今週の特売品（カンマ区切り、提案タブのマスト食材に使用）",
            key="sale_items",
            placeholder="例: 豚こま肉, 大根, 鮭",
        )

        col_all, col_clear = st.columns(2)
        with col_all:
            if st.button("全てチェック", key="shop_check_all"):
                for name in aggregated:
                    checked[name] = True
                save_shopping_state(checked)
                st.rerun()
        with col_clear:
            if st.button("チェックをリセット", key="shop_clear"):
                checked = {}
                st.session_state["shop_checked"] = checked
                save_shopping_state(checked)
                st.rerun()

        st.divider()

        # カテゴリ別チェックリスト
        any_changed = False
        for category, items in grouped.items():
            st.markdown(f"**{category}**")
            for name, info in items:
                amount_str = format_amount(info)
                recipe_hint = "、".join(info["recipes"][:2])
                col_chk, col_info = st.columns([1, 5])
                with col_chk:
                    prev = checked.get(name, False)
                    new_val = st.checkbox(
                        name,
                        value=prev,
                        key=f"shop_{name}",
                        label_visibility="collapsed",
                    )
                    if new_val != prev:
                        checked[name] = new_val
                        any_changed = True
                with col_info:
                    done_style = "text-decoration: line-through; color: #aaa;" if checked.get(name) else ""
                    st.markdown(
                        f"<div class='shop-item' style='{done_style}'>"
                        f"<b>{name}</b>（{amount_str}）"
                        f"<span style='color:#888;font-size:0.8rem'> ← {recipe_hint}</span>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

        if any_changed:
            save_shopping_state(checked)

        st.divider()
        st.markdown("#### 📋 クリップボード用テキスト")
        clipboard_text = build_clipboard_text(grouped, checked)
        st.text_area("コピー用", clipboard_text, height=250, key="clipboard_text_area")


# ========== Tab 4: 今日の食事記録 ==========
with tab4:
    today_str = date.today().isoformat()
    st.title("📝 今日の食事記録")
    st.caption(f"📅 {today_str} の夕食")

    staple_foods = get_staple_foods()
    ready_made_items = load_ready_made()

    weekly_ids = get_all_selected_ids()
    weekly_recipes = [get_recipe_by_id(rid, recipes) for rid in weekly_ids]
    weekly_recipes = [r for r in weekly_recipes if r is not None]

    def build_log_from_widgets() -> dict:
        persons = {}
        for person_key in ["husband", "wife", "child"]:
            recipe_items = []
            for r in weekly_recipes:
                if st.session_state.get(f"rcp_check_{person_key}_{r['id']}", False):
                    amount_key = f"rcp_amount_{person_key}_{r['id']}"
                    default_g = r.get("serving_size_adult_g", 80) if person_key != "child" else r.get("serving_size_child_g", 40)
                    amount_g = st.session_state.get(amount_key, default_g)
                    recipe_items.append({"recipe_id": r["id"], "amount_g": amount_g})

            staple_items = []
            staple_name = st.session_state.get(f"staple_sel_{person_key}", "なし")
            if staple_name != "なし":
                staple = next((s for s in staple_foods if s["name"] == staple_name), None)
                if staple:
                    default_g = staple.get("default_amount_adult_g", 150) if person_key != "child" else staple.get("default_amount_child_g", 80)
                    amount_g = st.session_state.get(f"staple_amount_{person_key}", default_g)
                    staple_items.append({"staple_id": staple["id"], "amount_g": amount_g})

            ready_made_logs = []
            for item in ready_made_items:
                if st.session_state.get(f"rm_check_{person_key}_{item['id']}", False):
                    default_g = item.get("default_amount_g", 50) if person_key != "child" else max(item.get("default_amount_g", 50) // 2, 1)
                    amount_g = st.session_state.get(f"rm_amount_{person_key}_{item['id']}", default_g)
                    ready_made_logs.append({"ready_made_id": item["id"], "amount_g": amount_g})

            persons[person_key] = {
                "recipe_items": recipe_items,
                "staple_items": staple_items,
                "ready_made_items": ready_made_logs,
            }
        return persons

    if "meal_log_loaded" not in st.session_state:
        saved_log = load_daily_log()
        today_log = get_today_log(saved_log)
        for person_key in ["husband", "wife", "child"]:
            plog = today_log.get(person_key, build_empty_person_log())
            for item in plog.get("recipe_items", []):
                rid = item["recipe_id"]
                st.session_state[f"rcp_check_{person_key}_{rid}"] = True
                st.session_state[f"rcp_amount_{person_key}_{rid}"] = item["amount_g"]
            for item in plog.get("staple_items", []):
                sid = item["staple_id"]
                staple = next((s for s in staple_foods if s["id"] == sid), None)
                if staple:
                    st.session_state[f"staple_sel_{person_key}"] = staple["name"]
                    st.session_state[f"staple_amount_{person_key}"] = item["amount_g"]
            for item in plog.get("ready_made_items", []):
                rid = item["ready_made_id"]
                st.session_state[f"rm_check_{person_key}_{rid}"] = True
                st.session_state[f"rm_amount_{person_key}_{rid}"] = item["amount_g"]
        st.session_state["meal_log_loaded"] = True

    PERSON_LABELS = {
        "husband": "👨 夫",
        "wife": "🤰 妻",
        "child": "👦 子供",
    }

    # ---- Section 1: 作り置きから選ぶ ----
    st.subheader("🍱 作り置きから選ぶ")
    if not weekly_recipes:
        st.info("「献立」タブでレシピを選んでください。")
    else:
        for r in weekly_recipes:
            cat_emoji = CAT_EMOJI.get(r["category"], "🍽")
            st.markdown(f"**{cat_emoji} {r['name']}**")
            rcols = st.columns(3)
            for col, person_key in zip(rcols, ["husband", "wife", "child"]):
                with col:
                    checked_rcp = st.checkbox(
                        PERSON_LABELS[person_key],
                        key=f"rcp_check_{person_key}_{r['id']}",
                    )
                    if checked_rcp:
                        default_g = r.get("serving_size_adult_g", 80) if person_key != "child" else r.get("serving_size_child_g", 40)
                        st.number_input(
                            "g",
                            min_value=0,
                            max_value=300,
                            value=default_g,
                            step=10,
                            key=f"rcp_amount_{person_key}_{r['id']}",
                            label_visibility="collapsed",
                        )

    st.divider()

    # ---- Section 2: ご飯類 ----
    st.subheader("🍚 ご飯類")
    staple_names = [s["name"] for s in staple_foods]
    pcols = st.columns(3)
    for col, person_key in zip(pcols, ["husband", "wife", "child"]):
        with col:
            st.markdown(f"**{PERSON_LABELS[person_key]}**")
            selected_name = st.selectbox(
                "種類",
                ["なし"] + staple_names,
                key=f"staple_sel_{person_key}",
                label_visibility="collapsed",
            )
            if selected_name != "なし":
                staple = next((s for s in staple_foods if s["name"] == selected_name), None)
                if staple:
                    default_g = staple.get("default_amount_adult_g", 150) if person_key != "child" else staple.get("default_amount_child_g", 80)
                    st.number_input(
                        "g",
                        min_value=0,
                        max_value=400,
                        value=default_g,
                        step=10,
                        key=f"staple_amount_{person_key}",
                        label_visibility="collapsed",
                    )

    st.divider()

    # ---- Section 3: 既製品 ----
    st.subheader("🛒 既製品")

    with st.expander("既製品マスタを管理（追加・削除）"):
        st.markdown("**新しい既製品を追加**")
        new_name = st.text_input("商品名", key="rm_new_name")
        new_default_g = st.number_input("デフォルト量(g)", min_value=1, value=50, key="rm_new_g")
        st.markdown("栄養成分（100gあたり）")
        nm_cols = st.columns(4)
        with nm_cols[0]:
            new_cal = st.number_input("kcal", min_value=0.0, value=100.0, key="rm_new_cal")
        with nm_cols[1]:
            new_prot = st.number_input("タンパク質g", min_value=0.0, value=5.0, key="rm_new_prot")
        with nm_cols[2]:
            new_iron = st.number_input("鉄mg", min_value=0.0, value=1.0, key="rm_new_iron")
        with nm_cols[3]:
            new_salt = st.number_input("塩分g", min_value=0.0, value=0.5, key="rm_new_salt")

        if st.button("追加する", key="rm_add_btn"):
            if new_name.strip():
                new_id = f"ready_{len(ready_made_items) + 1:03d}_custom"
                ready_made_items.append({
                    "id": new_id,
                    "name": new_name.strip(),
                    "default_amount_g": int(new_default_g),
                    "nutrition_per_100g": {
                        "calories": new_cal, "protein_g": new_prot,
                        "fat_g": 0.0, "carbs_g": 0.0, "salt_g": new_salt,
                        "iron_mg": new_iron, "calcium_mg": 0.0, "folate_ug": 0.0,
                    },
                })
                save_ready_made(ready_made_items)
                st.success(f"「{new_name.strip()}」を追加しました。")
                st.rerun()
            else:
                st.warning("商品名を入力してください。")

        st.markdown("**既製品を削除**")
        for item in ready_made_items:
            del_cols = st.columns([5, 1])
            with del_cols[0]:
                st.markdown(f"- {item['name']} ({item['default_amount_g']}g)")
            with del_cols[1]:
                if st.button("削除", key=f"rm_del_{item['id']}"):
                    ready_made_items = [i for i in ready_made_items if i["id"] != item["id"]]
                    save_ready_made(ready_made_items)
                    st.rerun()

    for item in ready_made_items:
        st.markdown(f"**{item['name']}**（デフォルト {item['default_amount_g']}g）")
        rm_cols = st.columns(3)
        for col, person_key in zip(rm_cols, ["husband", "wife", "child"]):
            with col:
                checked_rm = st.checkbox(
                    PERSON_LABELS[person_key],
                    key=f"rm_check_{person_key}_{item['id']}",
                )
                if checked_rm:
                    default_g = item.get("default_amount_g", 50) if person_key != "child" else max(item.get("default_amount_g", 50) // 2, 1)
                    st.number_input(
                        "g",
                        min_value=0,
                        max_value=500,
                        value=default_g,
                        step=5,
                        key=f"rm_amount_{person_key}_{item['id']}",
                        label_visibility="collapsed",
                    )

    st.divider()

    # ---- Section 4: 1食合計 ----
    st.subheader("📊 1食合計（夕食）")

    current_log = build_log_from_widgets()
    targets_map = {
        "husband": get_husband_dinner_targets(),
        "wife": get_pregnancy_dinner_targets(),
        "child": get_child_dinner_targets(),
    }

    nutr_cols = st.columns(3)
    for col, person_key in zip(nutr_cols, ["husband", "wife", "child"]):
        with col:
            st.markdown(f"**{PERSON_LABELS[person_key]}**")
            person_nutr = calc_person_nutrition(
                current_log[person_key], recipes, staple_foods, ready_made_items
            )
            targets = targets_map[person_key]
            for key in ["calories", "protein_g", "iron_mg", "calcium_mg", "folate_ug", "salt_g"]:
                if key not in targets:
                    continue
                label = get_nutrient_label(key)
                unit = get_nutrient_unit(key)
                val = person_nutr.get(key, 0)
                target = targets[key]
                ratio = val / target if target > 0 else 0
                bar_val = min(ratio, 1.0)
                st.markdown(
                    f"<span style='font-size:0.8rem'>{label}：{val:.1f}{unit} ({ratio*100:.0f}%)</span>",
                    unsafe_allow_html=True,
                )
                st.progress(bar_val)

    st.divider()
    if st.button("💾 今日の記録を保存", key="save_meal_log", use_container_width=True):
        log = load_daily_log()
        if today_str not in log:
            log[today_str] = {}
        log[today_str]["dinner"] = current_log
        save_daily_log(log)
        st.success(f"✅ {today_str} の夕食記録を保存しました！")


# ========== Tab 5: 栄養サマリー ==========
with tab5:
    st.title("🥗 栄養サマリー")

    all_ids = get_all_selected_ids()

    if not all_ids:
        st.info("「献立」タブでレシピを選ぶと、栄養サマリーが表示されます。")
    else:
        per_person = calc_nutrition_per_person(all_ids, recipes)
        pregnancy_targets = get_pregnancy_dinner_targets()
        child_targets = get_child_dinner_targets()

        st.markdown(f"**選択中のレシピ ({len(all_ids)}品)**")
        for rid in all_ids:
            r = get_recipe_by_id(rid, recipes)
            if r:
                cat_emoji = CAT_EMOJI.get(r["category"], "🍽")
                st.markdown(f"- {cat_emoji} {r['name']}")

        st.divider()
        st.markdown("## 🤰 妻（妊婦後期）の栄養充足率")
        st.caption("夕食1人前として、妊婦後期の夕食推奨量（1日の35%）との比較")

        for key in ["calories", "iron_mg", "calcium_mg", "folate_ug", "salt_g", "protein_g"]:
            label = get_nutrient_label(key)
            unit = get_nutrient_unit(key)
            target = pregnancy_targets.get(key, 0)
            value = per_person.get(key, 0)
            ratio = value / target if target > 0 else 0
            upper = is_upper_limit(key)
            if upper:
                status = "🔴 超過" if ratio > 1.0 else "🟢 OK"
            else:
                status = "🟢 十分" if ratio >= 0.9 else ("🟡 やや不足" if ratio >= 0.6 else "🔴 不足")
            st.markdown(f"**{label}**　{value:.1f} {unit} / 目標 {target:.1f} {unit}　{status}　({ratio*100:.0f}%)")
            st.progress(min(ratio, 1.0))

        st.divider()
        st.markdown("## 👦 子供（4歳）の栄養充足率")
        st.caption("夕食1人前として、4歳児の夕食推奨量（1日の35%）との比較")

        for key in ["calories", "protein_g", "salt_g", "iron_mg", "calcium_mg"]:
            label = get_nutrient_label(key)
            unit = get_nutrient_unit(key)
            target = child_targets.get(key, 0)
            value = per_person.get(key, 0)
            ratio = value / target if target > 0 else 0
            upper = is_upper_limit(key)
            if upper:
                status = "🔴 超過" if ratio > 1.0 else "🟢 OK"
            else:
                status = "🟢 十分" if ratio >= 0.9 else ("🟡 やや不足" if ratio >= 0.6 else "🔴 不足")
            st.markdown(f"**{label}**　{value:.1f} {unit} / 目標 {target:.1f} {unit}　{status}　({ratio*100:.0f}%)")
            st.progress(min(ratio, 1.0))

        st.divider()
        st.markdown("## 📊 詳細栄養テーブル（1人前）")
        nutr_keys = ["calories", "protein_g", "fat_g", "carbs_g", "salt_g", "iron_mg", "calcium_mg", "folate_ug"]
        rows = []
        husband_targets = get_husband_dinner_targets()
        for key in nutr_keys:
            val = per_person.get(key, 0)
            p_t = pregnancy_targets.get(key, 0)
            c_t = child_targets.get(key, 0)
            h_t = husband_targets.get(key, 0)
            rows.append({
                "栄養素": f"{get_nutrient_label(key)}（{get_nutrient_unit(key)}）",
                "今週(夕食1人前)": f"{val:.1f}",
                "妻目標": f"{p_t:.1f}",
                "妻充足率": f"{val/p_t*100:.0f}%" if p_t > 0 else "-",
                "子供目標": f"{c_t:.1f}",
                "子供充足率": f"{val/c_t*100:.0f}%" if c_t > 0 else "-",
                "夫目標": f"{h_t:.1f}",
                "夫充足率": f"{val/h_t*100:.0f}%" if h_t > 0 else "-",
            })
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


# ========== Tab 6: 献立を提案 ==========
with tab6:
    st.title("✨ 今週の献立を提案")

    with st.expander("⚙️ 品数設定", expanded=True):
        sc1, sc2, sc3, sc4 = st.columns(4)
        with sc1:
            sug_main = st.slider("🍖 主菜", 1, 6, 4, key="sug_main")
        with sc2:
            sug_side = st.slider("🥗 副菜", 1, 6, 4, key="sug_side")
        with sc3:
            sug_soup = st.slider("🍲 スープ", 0, 2, 1, key="sug_soup")
        with sc4:
            sug_pressure = st.slider("⚡ 圧力鍋", 0, 3, 0, key="sug_pressure")

    # 特売品リンク（買い出しタブの入力を引用）
    sale_items = st.session_state.get("sale_items", "")
    sale_list = [x.strip() for x in sale_items.split(",") if x.strip()]
    if sale_list:
        st.info(f"🏷️ 特売品を自動追加：{', '.join(sale_list)}")

    must_input = st.text_input(
        "マスト食材（カンマ区切り）",
        placeholder="例: 鶏もも肉, ほうれん草",
        key="must_input",
    )
    must_list = [x.strip() for x in must_input.split(",") if x.strip()] + sale_list
    must_list = list(dict.fromkeys(must_list))  # 重複除去（順序保持）

    if must_list:
        st.caption(f"対象食材：{', '.join(must_list)}")

    prioritize_fav = st.checkbox("★ お気に入り優先", key="sug_fav")

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("🔀 提案する", key="btn_suggest", use_container_width=True):
            seed = random.randint(0, 99999)
            st.session_state["suggestion_seed"] = seed
            st.session_state["suggestion"] = suggest_recipes(
                recipes, sug_main, sug_side, sug_soup, must_list, prioritize_fav,
                random_seed=seed, pressure_count=sug_pressure,
            )
    with col_btn2:
        if st.button("🔁 もう一度提案", key="btn_retry", use_container_width=True):
            seed = random.randint(0, 99999)
            st.session_state["suggestion_seed"] = seed
            st.session_state["suggestion"] = suggest_recipes(
                recipes, sug_main, sug_side, sug_soup, must_list, prioritize_fav,
                random_seed=seed, pressure_count=sug_pressure,
            )

    suggestion = st.session_state.get("suggestion")
    if suggestion:
        st.divider()
        st.markdown("### 📋 提案結果")

        for cat_key, cat_label in [("main", "🍖 主菜"), ("side", "🥗 副菜"), ("soup", "🍲 スープ"), ("pressure", "⚡ 圧力鍋")]:
            cat_recipes = suggestion.get(cat_key, [])
            if not cat_recipes:
                continue
            st.markdown(f"**{cat_label}**")
            for r in cat_recipes:
                star = "★" if r.get("favorite") else "☆"
                card_cls = "recipe-card-pressure" if cat_key == "pressure" else "recipe-card"
                st.markdown(
                    f"<div class='{card_cls}'>"
                    f"<div class='recipe-card-name'>{star} {r['name']}</div>"
                    f"<div class='recipe-card-meta'>⏱ {r['prep_time_min'] + r['cook_time_min']}分 &nbsp;|&nbsp; 🗓 {r['storage_days']}日保存</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

        # 提案の栄養サマリー
        sug_ids = []
        for key in ["main", "side", "soup", "pressure"]:
            sug_ids.extend([r["id"] for r in suggestion.get(key, [])])
        if sug_ids:
            per_p = calc_nutrition_per_person(sug_ids, recipes)
            st.markdown("#### 栄養サマリー（この献立の1人前）")
            scol1, scol2 = st.columns(2)
            with scol1:
                render_nutrition_bars("🤰 妻", get_pregnancy_dinner_targets(), per_p, PREGNANCY_DAILY)
            with scol2:
                render_nutrition_bars("👦 子供", get_child_dinner_targets(), per_p, CHILD_DAILY)

        st.divider()
        if st.button("✅ この献立で決定する", key="btn_decide", use_container_width=True):
            plan = st.session_state.weekly_plan
            plan["settings"]["main_count"] = sug_main
            plan["settings"]["side_count"] = sug_side
            plan["settings"]["soup_count"] = sug_soup
            plan["settings"]["pressure_count"] = sug_pressure
            plan["selected_recipes"]["main"] = [r["id"] for r in suggestion.get("main", [])]
            plan["selected_recipes"]["side"] = [r["id"] for r in suggestion.get("side", [])]
            plan["selected_recipes"]["soup"] = [r["id"] for r in suggestion.get("soup", [])]
            plan["selected_recipes"]["pressure"] = [r["id"] for r in suggestion.get("pressure", [])]
            save_plan()
            st.session_state.pop("suggestion", None)
            st.success("献立を保存しました！「献立」タブで確認できます。")
            st.rerun()
