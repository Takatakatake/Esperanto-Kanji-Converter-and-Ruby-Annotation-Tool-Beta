# multiprocessing_4c_10t.py (メインの Streamlit アプリ)

import streamlit as st
import re
import io
import json
import pandas as pd  # 使っていれば
from typing import List, Dict, Tuple, Optional
import multiprocessing

# ★★★ ここが肝心 ★★★
#   先ほど作成した esp_mod.py から「関数や辞書」をインポート
from esp_mod import (
    parallel_process,
    # orchestrate_comprehensive_esperanto_text_replacement,  # (必要なら)
    # もし必要なら、他の関数も
)

# もし set_start_method を明示したい場合は、トップレベルで行う (例)
# ただし、Streamlit 実行時の挙動を見ながら、外す場合も
if __name__ == "__main__":
    multiprocessing.set_start_method('spawn', force=True)
# これを入れると、Streamlit がコードを再実行するたびに「すでに set_start_method が実行されてる」警告が出ることがあるので注意

st.title("エスペラント文を漢字置換したり、HTML形式の訳ルビを振ったりする")

# 1) JSONファイル (置換ルール) をロードする
#   - デフォルト or アップロード
selected_option = st.radio(
    "JSONファイルをどうしますか？ (置換用JSONファイルの読み込み)",
    ("デフォルトを使用する", "アップロードする")
)

replacements_final_list = None
replacements_list_for_localized_string = None
replacements_list_for_2char = None

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

# 2) ここで placeholders (占位符置換用のリスト) も読み込む
def import_placeholders(filename: str) -> List[str]:
    with open(filename, 'r') as file:
        return [line.strip() for line in file if line.strip()]

placeholders_for_skipping_replacements = import_placeholders('./Appの运行に使用する各类文件/占位符(placeholders)_%1854%-%4934%_文字列替换skip用.txt')
placeholders_for_localized_replacement = import_placeholders('./Appの运行に使用する各类文件/占位符(placeholders)_@5134@-@9728@_局部文字列替换结果捕捉用.txt')

format_type = "HTML格式_Ruby文字_大小调整"  # 仮置き: あなたのUIロジックに合わせて再現

num_processes = 5
text_repeat_times = 10

# 3) Streamlit UI
with st.form(key='profile_form'):
    letter_type = st.radio('出力文字形式', ('上付き文字', 'x 形式', '^ 形式'))
    text0 = st.text_area("エスペラントの文章")
    submit_btn = st.form_submit_button('送信')
    cancel_btn = st.form_submit_button('キャンセル')

    if submit_btn:
        # ★★★ ここで並列処理を呼び出す ★★★
        #   すべての必要な引数を parallel_process に渡す
        processed_text = parallel_process(
            text=text0 * text_repeat_times,
            num_processes=num_processes,
            placeholders_for_skipping_replacements=placeholders_for_skipping_replacements,
            replacements_list_for_localized_string=replacements_list_for_localized_string,
            placeholders_for_localized_replacement=placeholders_for_localized_replacement,
            replacements_final_list=replacements_final_list,
            replacements_list_for_2char=replacements_list_for_2char,
            format_type=format_type
        )

        # ここで加工後のテキストを、HTMLとしてレンダリング or ダウンロード etc
        st.text_area("文字列置換後のテキスト(プレビュー)", processed_text, height=300)

        # ダウンロードボタン
        download_data = io.BytesIO(processed_text.encode('utf-8'))
        st.download_button(
            label="ダウンロード",
            data=download_data,
            file_name="processed_text.html",
            mime="text/html"
        )

st.title("アプリのGitHubリポジトリ")
st.markdown("https://github.com/Takatakatake/Esperanto-Kanji-Converter-and-Ruby-Annotation-Tool-")
