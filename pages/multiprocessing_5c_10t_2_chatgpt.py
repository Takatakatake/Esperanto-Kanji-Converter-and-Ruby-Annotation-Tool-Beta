# multiprocessing_4c_10t.py
# ------------------------
# メインの Streamlit アプリ (サンプル実装)

import streamlit as st
import re
import io
import json
import pandas as pd  # 必要な場合のみ
from typing import List, Dict, Tuple, Optional
import multiprocessing

# ★★★ ここが肝心 ★★★
#   先ほど作成した esp_mod.py (同一フォルダにあると仮定) から「並列処理関数 parallel_process」をインポート
from esp_mod import (
    # --- 辞書(字上符変換) ---
    x_to_circumflex,
    circumflex_to_x,
    x_to_hat,
    hat_to_x,
    hat_to_circumflex,
    circumflex_to_hat,

    # --- 関数(文字変換・処理) ---
    replace_esperanto_chars,
    convert_to_circumflex,
    unify_halfwidth_spaces,
    wrap_text_with_ruby,
    safe_replace,

    # --- 占位符関連 ---
    find_strings_in_text,
    create_replacements_list_for_intact_parts,
    find_strings_in_text_for_localized_replacement,
    create_replacements_list_for_localized_replacement,

    # --- メイン変換とマルチプロセス処理 ---
    orchestrate_comprehensive_esperanto_text_replacement,
    process_segment,
    parallel_process
)


# ▼ Windows/Macの場合、PicklingError回避のため 'spawn' を明示 (Streamlitとの相性に注意) ▼
if __name__ == "__main__":
    multiprocessing.set_start_method('spawn', force=True)
#   Streamlit で何度も再実行されると「すでに set_start_method が実行済み」の警告が出ることがあります。
#   警告だけで処理は続行されますが、もし煩わしければ以下を削除 or try/except で回避してください。
# ----------------------------------------------------------------------------------------------

st.title("エスペラント文を漢字置換したり、HTML形式の訳ルビを振ったりする")

# ==========================================================
# 1) JSONファイル (置換ルール) をロードする (デフォルト or アップロード)
# ==========================================================

selected_option = st.radio(
    "JSONファイルをどうしますか？ (置換用JSONファイルの読み込み)",
    ("デフォルトを使用する", "アップロードする")
)

replacements_final_list: List[Tuple[str, str, str]] = []
replacements_list_for_localized_string: List[Tuple[str, str, str]] = []
replacements_list_for_2char: List[Tuple[str, str, str]] = []

if selected_option == "デフォルトを使用する":
    default_json_path = "./Appの运行に使用する各类文件/最终的な替换用リスト(列表)(合并3个JSON文件).json"
    try:
        with open(default_json_path, 'r', encoding='utf-8') as f:
            combined_data = json.load(f)
            replacements_final_list = combined_data.get("全域替换用のリスト(列表)型配列(replacements_final_list)", [])
            replacements_list_for_localized_string = combined_data.get("局部文字替换用のリスト(列表)型配列(replacements_list_for_localized_string)", [])
            replacements_list_for_2char = combined_data.get("二文字词根替换用のリスト(列表)型配列(replacements_list_for_2char)", [])
        st.success("デフォルトJSONの読み込みに成功しました。")
    except Exception as e:
        st.error(f"JSONファイルの読み込みに失敗: {e}")
        st.stop()
else:
    uploaded_file = st.file_uploader("JSONファイルをアップロード (合并3个JSON文件).json 形式)", type="json")
    if uploaded_file is not None:
        try:
            combined_data = json.load(uploaded_file)
            replacements_final_list = combined_data.get("全域替换用のリスト(列表)型配列(replacements_final_list)", [])
            replacements_list_for_localized_string = combined_data.get("局部文字替换用のリスト(列表)型配列(replacements_list_for_localized_string)", [])
            replacements_list_for_2char = combined_data.get("二文字词根替换用のリスト(列表)型配列(replacements_list_for_2char)", [])
            st.success("アップロードしたJSONの読み込みに成功しました。")
        except Exception as e:
            st.error(f"アップロードJSONファイルの読み込みに失敗: {e}")
            st.stop()
    else:
        st.warning("JSONファイルがアップロードされていません。処理を停止します。")
        st.stop()

# ==========================================================
# 2) placeholders (占位符) の読み込み
# ==========================================================

def import_placeholders(filename: str) -> List[str]:
    """
    テキストファイルからplaceholder文字列を読み込み、リストにして返す。
    1行につき1つのplaceholderが入っている想定。
    """
    with open(filename, 'r', encoding='utf-8') as file:
        return [line.strip() for line in file if line.strip()]

# %...% のスキップ部分
placeholders_for_skipping_replacements: List[str] = import_placeholders(
    './Appの运行に使用する各类文件/占位符(placeholders)_%1854%-%4934%_文字列替换skip用.txt'
)
# @...@ の局所置換捕捉部分
placeholders_for_localized_replacement: List[str] = import_placeholders(
    './Appの运行に使用する各类文件/占位符(placeholders)_@5134@-@9728@_局部文字列替换结果捕捉用.txt'
)

# ==========================================================
# 3) ユーザー設定 (UI)
# ==========================================================

# (例) format_type は HTMLでルビを振るモードを仮に指定しておく
# 実際には、SelectBoxやRadio等で切り替えてもOK
format_type = "HTML格式_Ruby文字_大小调整"  # 例

# CPUプロセス数 (任意の値、少なければ並列度が下がり、多すぎるとリソースを食う)
num_processes = 5

# 同じテキストを何度繰り返すか (あえて大きめに設定して並列処理効果をテスト)
text_repeat_times = 10

# フォームでユーザー入力を受け取る
with st.form(key='profile_form'):
    letter_type = st.radio('出力文字形式', ('上付き文字', 'x 形式', '^ 形式'))
    text0 = st.text_area("エスペラントの文章", height=150)
    submit_btn = st.form_submit_button('送信')
    cancel_btn = st.form_submit_button('キャンセル')

    if submit_btn:
        # ==========================================================
        # ★★★ 4) 並列処理を呼び出す ★★★
        # ==========================================================
        # text0 を複製し (text_repeat_times 回)、parallel_processへ渡す
        repeated_text = text0 * text_repeat_times

        processed_text = parallel_process(
            text=repeated_text,
            num_processes=num_processes,
            placeholders_for_skipping_replacements=placeholders_for_skipping_replacements,
            replacements_list_for_localized_string=replacements_list_for_localized_string,
            placeholders_for_localized_replacement=placeholders_for_localized_replacement,
            replacements_final_list=replacements_final_list,
            replacements_list_for_2char=replacements_list_for_2char,
            format_type=format_type
        )

        # 結果表示
        st.text_area("文字列置換後のテキスト(プレビュー)", processed_text, height=300)

        # ダウンロードボタン (HTMLファイルとして保存する例)
        download_data = io.BytesIO(processed_text.encode('utf-8'))
        st.download_button(
            label="ダウンロード (HTML)",
            data=download_data,
            file_name="processed_text.html",
            mime="text/html"
        )

# フッター的な表示
st.title("アプリのGitHubリポジトリ")
st.markdown("https://github.com/Takatakatake/Esperanto-Kanji-Converter-and-Ruby-Annotation-Tool-")
