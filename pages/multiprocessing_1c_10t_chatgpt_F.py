# multiprocessing_5c_10t_2_chatgpt.py
# ------------------------------------
# メインの Streamlit アプリ (サンプル実装)

import streamlit as st
import re
import io
import json
import pandas as pd  # 必要なら使う
from typing import List, Dict, Tuple, Optional
import multiprocessing

# ★★★ ここが肝心 ★★★
#   同一フォルダにある esp_mod.py から、
#   全ての関数・辞書をまとめてインポートする例
from esp_mod_chatgpt2 import (
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

    find_strings_in_text,
    create_replacements_list_for_intact_parts,
    find_strings_in_text_for_localized_replacement,
    create_replacements_list_for_localized_replacement,

    orchestrate_comprehensive_esperanto_text_replacement,
    process_segment,
    parallel_process
)


# ▼ Windows/Macでの PicklingError回避のため 'spawn' を明示:
#   Streamlit でリロードされる度に「すでに設定済み」という警告が出る可能性があります。
if __name__ == "__main__":
    multiprocessing.set_start_method('spawn', force=True)


st.title("エスペラント文を漢字置換したり、HTML形式の訳ルビを振ったりする")

# ==========================================================
# 1) JSONファイル (置換ルール) をロードする
#    (デフォルト or アップロード)
# ==========================================================

selected_option = st.radio(
    "JSONファイルをどうしますか？ (置換用JSONファイルの読み込み)",
    ("デフォルトを使用する", "アップロードする")
)

# 置換ルールを格納する変数を初期化
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

# '%...%' のスキップ部分
placeholders_for_skipping_replacements: List[str] = import_placeholders(
    './Appの运行に使用する各类文件/占位符(placeholders)_%1854%-%4934%_文字列替换skip用.txt'
)

# '@...@' の局所置換捕捉部分
placeholders_for_localized_replacement: List[str] = import_placeholders(
    './Appの运行に使用する各类文件/占位符(placeholders)_@5134@-@9728@_局部文字列替换结果捕捉用.txt'
)

# ==========================================================
# 3) 設定パラメータ (UI)
# ==========================================================

# 例: 出力形式など。必要に応じてカスタマイズ。
format_type = "HTML格式_Ruby文字_大小调整"  # 例: ルビ付きHTML
num_processes,text_repeat_times = 1, 10


# ==========================================================
# 4) フォーム: ユーザー入力
# ==========================================================

# フォームの外で、変数 processed_text を初期化
processed_text = ""

with st.form(key='profile_form'):
    letter_type = st.radio('出力文字形式', ('上付き文字', 'x 形式', '^ 形式'))
    text0 = st.text_area("エスペラントの文章を入力してください", height=150)

    submit_btn = st.form_submit_button('送信')
    cancel_btn = st.form_submit_button('キャンセル')

    if submit_btn:
        # テキストを複製して並列化効果をテスト
        repeated_text = text0 * text_repeat_times

        # 並列処理を呼び出し
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
                    
        if format_type in ('HTML格式_Ruby文字_大小调整','HTML格式_Ruby文字_大小调整_汉字替换'):
            # html形式におけるルビサイズの変更形式
            ruby_style_head="""<!DOCTYPE html>
        <html lang="ja">
        <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ほとんどの環境で動作するルビ表示</title>
        <style>

            :root {
            --ruby-color: blue;
            --ruby-font-size: 50%;
            }

            .text-S_S { font-size: 12px; }
            .text-M_M {
            font-size: 16px; 
            font-family: Arial, sans-serif;
            line-height: 1.6 !important; 
            display: block; /* ブロック要素として扱う */
            position: relative;
            }
            .text-L_L { font-size: 20px; }
            .text-X_X { font-size: 24px; }

            /* ▼ ルビ（フレックスでルビを上に表示） */
            ruby {
            display: inline-flex;
            flex-direction: column;
            align-items: center;
            vertical-align: top !important;
            line-height: 1.2 !important;
            margin: 0 !important;
            padding: 0 !important;
            }

            /* ▼ ルビサイズクラス（例） */
            .ruby-XXXS_S { --ruby-font-size: 30%; }
            .ruby-XXS_S { --ruby-font-size: 30%; }
            .ruby-XS_S  { --ruby-font-size: 30%; }
            .ruby-S_S   { --ruby-font-size: 40%; }
            .ruby-M_M   { --ruby-font-size: 50%; }
            .ruby-L_L   { --ruby-font-size: 60%; }
            .ruby-XL_L  { --ruby-font-size: 70%; }
            .ruby-XXL_L { --ruby-font-size: 80%; }

            /* ▼ 追加マイナス余白（ルビサイズ別に上書き） */
            rt {
            display: block !important;
            font-size: var(--ruby-font-size);
            color: var(--ruby-color);
            line-height: 1.05;/*ルビを改行するケースにおけるルビの行間*/
            text-align: center;
            /* margin-top: 0.2em !important;   
            transform: translateY(0.4em) !important; */
            }
            rt.ruby-XXXS_S {
            margin-top: -0em !important;/*結局ここは0が一番良かった。 */
            transform: translateY(-6.6em) !important;/* ルビの高さ位置はここで調節する。 */
            }    
            rt.ruby-XXS_S {
            margin-top: -0em !important;/*結局ここは0が一番良かった。 */
            transform: translateY(-5.6em) !important;/* ルビの高さ位置はここで調節する。 */
            }
            rt.ruby-XS_S {
            transform: translateY(-4.6em) !important;
            }
            rt.ruby-S_S {
            transform: translateY(-3.7em) !important;
            }
            rt.ruby-M_M {
            transform: translateY(-3.1em) !important;
            }
            rt.ruby-L_L {
            transform: translateY(-2.8em) !important;
            }
            rt.ruby-XL_L {
            transform: translateY(-2.5em) !important;
            }
            rt.ruby-XXL_L {
            transform: translateY(-2.3em) !important;
            }

        </style>
        </head>
        <body>
        <p class="text-M_M">
        """
            ruby_style_tail = """  </p>

        </body>
        </html>"""


        elif format_type in ('HTML格式','HTML格式_汉字替换'):
            # ルビのスタイルは最小限
            ruby_style_head = """<style>
        ruby rt {
        color: blue;
        }
        </style>
        """
            ruby_style_tail="<br>"
        else:
            ruby_style_head=""
            ruby_style_tail=""

        processed_text = ruby_style_head+processed_text+ruby_style_tail

# =========================================
# フォームを出た後の処理 (ダウンロードボタン 等)
# =========================================

# フォーム外なら、st.download_button が使用可能
if processed_text:
    # 結果プレビュー
    st.text_area("文字列置換後のテキスト(プレビュー)", processed_text, height=300)

    # ダウンロードボタン (HTMLファイルとして)
    download_data = processed_text.encode('utf-8')
    st.download_button(
        label="ダウンロード (HTML)",
        data=download_data,
        file_name="processed_text.html",
        mime="text/html"
    )

# フッター的な表示
st.title("アプリのGitHubリポジトリ")
st.markdown("https://github.com/Takatakatake/Esperanto-Kanji-Converter-and-Ruby-Annotation-Tool-")
