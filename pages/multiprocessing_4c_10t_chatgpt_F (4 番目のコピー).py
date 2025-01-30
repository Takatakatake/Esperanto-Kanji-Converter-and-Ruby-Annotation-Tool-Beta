# streamlit_app_detailed_settings_toggle.py
# -----------------------------------------
# "詳細設定"が閉じているときはシングルコア + text_repeat_times=1
# "詳細設定"を開いた瞬間に、並列処理オン + num_processes=4 がデフォルトになる

import streamlit as st
import re
import io
import json
import pandas as pd
from typing import List, Tuple
import multiprocessing

# ======== 外部モジュール (esp_text_replacement_module.py) からインポート ========
from esp_text_replacement_module import (
    x_to_circumflex,
    circumflex_to_x,
    x_to_hat,
    hat_to_x,
    hat_to_circumflex,
    circumflex_to_hat,

    replace_esperanto_chars,
    convert_to_circumflex,
    unify_halfwidth_spaces,
    wrap_text_with_ruby,
    safe_replace,
    import_placeholders,

    find_percent_enclosed_strings_for_skipping_replacement,
    create_replacements_list_for_intact_parts,
    find_at_enclosed_strings_for_localized_replacement,
    create_replacements_list_for_localized_replacement,

    orchestrate_comprehensive_esperanto_text_replacement,
    process_segment,
    parallel_process
)

# Windows/MacでのPicklingError回避
if __name__ == "__main__":
    multiprocessing.set_start_method('spawn', force=True)


st.title("エスペラント文を漢字置換 + HTML訳ルビ (詳細設定の開閉で挙動を変える)")

# ----------------------------------------------------------------
# 1) JSONファイルの読み込み (デフォルト or アップロード)
# ----------------------------------------------------------------
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

# ----------------------------------------------------------------
# 2) placeholders (占位符) の読み込み
# ----------------------------------------------------------------
placeholders_for_skipping_replacements = import_placeholders(
    './Appの运行に使用する各类文件/占位符(placeholders)_%1854%-%4934%_文字列替换skip用.txt'
)
placeholders_for_localized_replacement = import_placeholders(
    './Appの运行に使用する各类文件/占位符(placeholders)_@5134@-@9728@_局部文字列替换结果捕捉用.txt'
)

# ----------------------------------------------------------------
# 3) 詳細設定の "開く/閉じる" チェックボックス
#    閉じている: シングルコア, text_repeat_times=1
#    開いている: 並列処理ON(default), num_processes=4, text_repeat_times=2(等)
# ----------------------------------------------------------------
detail_open = st.checkbox("詳細設定を開く", value=False)

# 初期値 (詳細設定を閉じている状態のデフォルト)
use_parallel = False
num_processes = 1
text_repeat_times = 1

if detail_open:
    st.markdown("**詳細設定が開かれています** : 以下の値を変更可。")
    # デフォルトで並列処理オン, num_processes=4
    use_parallel = st.checkbox("並列処理を使う (テキストが多い場合に高速化)", value=True)
    num_processes = st.number_input("同時プロセス数 (CPUコア数や環境による)", min_value=1, max_value=32, value=4, step=1)
    text_repeat_times = st.slider("テキストの複製回数 (テスト用)", min_value=1, max_value=20, value=1)
else:
    st.markdown("**詳細設定は閉じています**。現在は以下のデフォルトを使用します。\n"
                "- シングルコア (並列処理なし)\n"
                "- text_repeat_times = 1\n"
                "\n"
                "詳細設定を開くと、並列処理オプションなどが使用できます。")

st.write("---")

# ----------------------------------------------------------------
# 4) 出力形式 (format_type) を選択
# ----------------------------------------------------------------
format_type = st.selectbox(
    "出力形式 (ルビなどの設定)",
    [
        "HTML格式_Ruby文字_大小调整",
        "HTML格式_Ruby文字_大小调整_汉字替换",
        "HTML格式",
        "HTML格式_汉字替换",
        "括弧(号)格式",
        "括弧(号)格式_汉字替换",
        "替换后文字列のみ(仅)保留(简单替换)"
    ]
)

# ----------------------------------------------------------------
# 5) 入力テキスト
# ----------------------------------------------------------------
st.subheader("エスペラントの文章を入力してください")
text0 = st.text_area("文章", height=150)

letter_type = st.radio('出力文字形式', ('上付き文字', 'x 形式', '^形式'))

submit_btn = st.button("送信")
processed_text = ""

if submit_btn:
    # ----------------------------------------------------------------
    # テキストを複製
    # ----------------------------------------------------------------
    repeated_text = text0 * text_repeat_times

    # ----------------------------------------------------------------
    # 並列処理 or シングル処理
    # ----------------------------------------------------------------
    if use_parallel:
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
    else:
        # シングルスレッド
        processed_text = orchestrate_comprehensive_esperanto_text_replacement(
            text=repeated_text,
            placeholders_for_skipping_replacements=placeholders_for_skipping_replacements,
            replacements_list_for_localized_string=replacements_list_for_localized_string,
            placeholders_for_localized_replacement=placeholders_for_localized_replacement,
            replacements_final_list=replacements_final_list,
            replacements_list_for_2char=replacements_list_for_2char,
            format_type=format_type
        )

    # ----------------------------------------------------------------
    # 出力文字形式 (letter_type)
    # ----------------------------------------------------------------
    if letter_type == '上付き文字':
        processed_text = replace_esperanto_chars(processed_text, x_to_circumflex)
        processed_text = replace_esperanto_chars(processed_text, hat_to_circumflex)
    elif letter_type == '^形式':
        processed_text = replace_esperanto_chars(processed_text, x_to_hat)
        processed_text = replace_esperanto_chars(processed_text, circumflex_to_hat)

    # ----------------------------------------------------------------
    # HTMLの見た目をさらに整形 (format_type 依存)
    # ----------------------------------------------------------------
    if format_type in ('HTML格式_Ruby文字_大小调整','HTML格式_Ruby文字_大小调整_汉字替换'):
        ruby_style_head = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ほとんどの環境で動作するルビ表示</title>
<style>
  /* ここにルビCSS ... (省略 or 前述) */
</style>
</head>
<body>
<p class="text-M_M">
"""
        ruby_style_tail = "</p></body></html>"
    elif format_type in ('HTML格式','HTML格式_汉字替换'):
        ruby_style_head = """<style>
ruby rt {
    color: blue;
}
</style>
"""
        ruby_style_tail = "<br>"
    else:
        ruby_style_head = ""
        ruby_style_tail = ""

    processed_text = ruby_style_head + processed_text + ruby_style_tail


# ----------------------------------------------------------------
# 最後に、結果プレビュー & ダウンロード
# ----------------------------------------------------------------
if processed_text:
    st.text_area("文字列置換後のテキスト(プレビュー)", processed_text, height=300)

    download_data = processed_text.encode('utf-8')
    st.download_button(
        label="ダウンロード (HTML)",
        data=download_data,
        file_name="processed_text.html",
        mime="text/html"
    )

st.write("---")
st.title("アプリのGitHubリポジトリ")
st.markdown("https://github.com/Takatakatake/Esperanto-Kanji-Converter-and-Ruby-Annotation-Tool-")
