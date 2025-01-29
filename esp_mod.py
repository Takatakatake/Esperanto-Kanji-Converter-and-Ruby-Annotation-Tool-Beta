# esp_mod.py
# ----------
# Pythonファイル単独でモジュールとして扱う想定。トップレベルに各関数を定義しておく。

import re
import json
from typing import List, Tuple, Dict
import multiprocessing
from bs4 import BeautifulSoup, NavigableString
from bs4.element import Tag

# ================================
# 1) エスペラント文字変換用の辞書
# ================================
x_to_circumflex = {
    'cx': 'ĉ', 'gx': 'ĝ', 'hx': 'ĥ', 'jx': 'ĵ', 'sx': 'ŝ', 'ux': 'ŭ',
    'Cx': 'Ĉ', 'Gx': 'Ĝ', 'Hx': 'Ĥ', 'Jx': 'Ĵ', 'Sx': 'Ŝ', 'Ux': 'Ŭ'
}
circumflex_to_x = {
    'ĉ': 'cx', 'ĝ': 'gx', 'ĥ': 'hx', 'ĵ': 'jx', 'ŝ': 'sx', 'ŭ': 'ux',
    'Ĉ': 'Cx', 'Ĝ': 'Gx', 'Ĥ': 'Hx', 'Ĵ': 'Jx', 'Ŝ': 'Sx', 'Ŭ': 'Ux'
}
x_to_hat = {
    'cx': 'c^', 'gx': 'g^', 'hx': 'h^', 'jx': 'j^', 'sx': 's^', 'ux': 'u^',
    'Cx': 'C^', 'Gx': 'G^', 'Hx': 'H^', 'Jx': 'J^', 'Sx': 'S^', 'Ux': 'U^'
}
hat_to_x = {
    'c^': 'cx', 'g^': 'gx', 'h^': 'hx', 'j^': 'jx', 's^': 'sx', 'u^': 'ux',
    'C^': 'Cx', 'G^': 'Gx', 'H^': 'Hx', 'J^': 'Jx', 'S^': 'Sx', 'U^': 'Ux'
}
hat_to_circumflex = {
    'c^': 'ĉ', 'g^': 'ĝ', 'h^': 'ĥ', 'j^': 'ĵ', 's^': 'ŝ', 'u^': 'ŭ',
    'C^': 'Ĉ', 'G^': 'Ĝ', 'H^': 'Ĥ', 'J^': 'Ĵ', 'S^': 'Ŝ', 'U^': 'Ŭ'
}
circumflex_to_hat = {
    'ĉ': 'c^', 'ĝ': 'g^', 'ĥ': 'h^', 'ĵ': 'j^', 'ŝ': 's^', 'ŭ': 'u^',
    'Ĉ': 'C^', 'Ĝ': 'G^', 'Ĥ': 'H^', 'Ĵ': 'J^', 'Ŝ': 'S^', 'Ŭ': 'U^'
}

# ================================
# 2) 基本の置換関数
# ================================
def replace_esperanto_chars(text: str, char_dict: Dict[str, str]) -> str:
    """与えられた辞書 char_dict に基づいて text 内を一括置換。"""
    for original_char, converted_char in char_dict.items():
        text = text.replace(original_char, converted_char)
    return text

def convert_to_circumflex(text: str) -> str:
    """
    x形式(cx, gx等) や ^形式(c^, g^等) を、
    ĉ, ĝ, ĥ, ĵ, ŝ, ŭ の形式に統一する。
    """
    text = replace_esperanto_chars(text, hat_to_circumflex)
    text = replace_esperanto_chars(text, x_to_circumflex)
    return text

def unify_halfwidth_spaces(text: str) -> str:
    """
    全角スペース(U+3000)は維持し、それ以外の
    半角に見える特殊空白(U+00A0, U+2002..200A)を ASCIIスペースに統一。
    """
    pattern = r"[\u00A0\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200A]"
    return re.sub(pattern, " ", text)

# ================================
# 3) HTMLルビタグの補助関数
# ================================
def wrap_text_with_ruby(html_string: str, chunk_size: int = 10) -> str:
    """
    <ruby>タグのかかっていないテキスト部分にも強制的に <ruby> を被せて
    ルビ表示を行う。BeautifulSoupを使用。
    """
    soup = BeautifulSoup(html_string, 'lxml')

    def process_element(element: Tag, in_ruby: bool = False) -> None:
        if element.name in ['ruby', 'rt']:
            in_ruby = True

        for child in list(element.children):
            if isinstance(child, NavigableString):
                text_content = str(child)
                if not text_content.strip():
                    # 空白や改行のみの場合はスキップ
                    continue

                if in_ruby:
                    # すでにルビ要素内ならそのまま
                    continue

                # chunk_size毎に細切れ
                chunks = [text_content[i : i + chunk_size] for i in range(0, len(text_content), chunk_size)]
                new_tags = []
                for chunk in chunks:
                    chunk = chunk.replace(" ", "&nbsp;").replace("　", "&nbsp;&nbsp;")
                    ruby_tag = soup.new_tag('ruby')
                    ruby_tag.string = chunk
                    new_tags.append(ruby_tag)

                child.replace_with(*new_tags)

            elif child.name and child.name.lower() in ['script', 'style']:
                # script/style 内は編集しない
                continue
            else:
                # 再帰的に処理
                process_element(child, in_ruby)

    # 実行
    process_element(soup, in_ruby=False)

    # 不要な<html>, <body>を除去
    if soup.html:
        soup.html.unwrap()
    if soup.body:
        soup.body.unwrap()

    # 不要な<p> を外す(先頭と末尾だけ)
    if soup.contents and soup.contents[0].name == "p":
        soup.contents[0].unwrap()
    if soup.contents and soup.contents[-1].name == "p":
        soup.contents[-1].unwrap()

    # &amp;nbsp; → &nbsp; に戻す
    final_str = str(soup).replace("&amp;nbsp;", "&nbsp;")
    return final_str

# ================================
# 4) 占位符(placeholder)関連
# ================================
def safe_replace(text: str, replacements: List[Tuple[str, str, str]]) -> str:
    """
    (old, new, placeholder) のタプルを含むリストを受け取り、
    text中の old → placeholder → new の段階置換を行う。
    """
    valid_replacements = {}
    # old → placeholder
    for old, new, ph in replacements:
        if old in text:
            text = text.replace(old, ph)
            valid_replacements[ph] = new
    # placeholder → new
    for ph, new_val in valid_replacements.items():
        text = text.replace(ph, new_val)
    return text

PERCENT_PATTERN = re.compile(r'%(.{1,50}?)%')

def find_strings_in_text(text: str) -> List[str]:
    """'%foo%' の形を全て抽出。50文字以内。"""
    matches = []
    used_indices = set()
    for match in PERCENT_PATTERN.finditer(text):
        start, end = match.span()
        if start not in used_indices and (end - 2) not in used_indices:
            matches.append(match.group(1))
            used_indices.update(range(start, end))
    return matches

def create_replacements_list_for_intact_parts(text: str, placeholders: List[str]) -> List[Tuple[str, str]]:
    """
    '%xxx%' を placeholders[i] に置換できるようリストを作る。
    例: '%天下%' → PLACEHOLDER_001
    """
    matches = find_strings_in_text(text)
    results = []
    for i, match in enumerate(matches):
        if i < len(placeholders):
            results.append((f"%{match}%", placeholders[i]))
        else:
            break
    return results

AT_PATTERN = re.compile(r'@(.{1,18}?)@')

def find_strings_in_text_for_localized_replacement(text: str) -> List[str]:
    """'@foo@' の形を全て抽出。18文字以内。"""
    matches = []
    used_indices = set()
    for match in AT_PATTERN.finditer(text):
        start, end = match.span()
        if start not in used_indices and (end - 2) not in used_indices:
            matches.append(match.group(1))
            used_indices.update(range(start, end))
    return matches

def create_replacements_list_for_localized_replacement(
    text: str,
    placeholders: List[str],
    replacements_list_for_localized_string: List[Tuple[str, str, str]]
) -> List[List[str]]:
    """
    '@xxx@' を placeholders[i] に一時置換し、その内部は safe_replace で局所的に変換する。
    """
    matches = find_strings_in_text_for_localized_replacement(text)
    tmp_list = []
    for i, match in enumerate(matches):
        if i < len(placeholders):
            replaced_match = safe_replace(match, replacements_list_for_localized_string)
            tmp_list.append([f"@{match}@", placeholders[i], replaced_match])
        else:
            break
    return tmp_list

# ================================
# 5) メインの複合置換関数
# ================================
def orchestrate_comprehensive_esperanto_text_replacement(
    text: str,
    placeholders_for_skipping_replacements: List[str],
    replacements_list_for_localized_string: List[Tuple[str, str, str]],
    placeholders_for_localized_replacement: List[str],
    replacements_final_list: List[Tuple[str, str, str]],
    replacements_list_for_2char: List[Tuple[str, str, str]],
    format_type: str
) -> str:
    """
    文章全体を複数段階で置換。
    1) 半角スペース正規化
    2) ĉ 等への変換
    3) %...% 保護
    4) @...@ 局所置換
    5) 大域置換
    6) 二文字語根の2段階置換
    7) placeholder復元
    8) 必要ならHTMLルビ化
    """
    # 1,2) 空白・エスペラント文字変換
    text = unify_halfwidth_spaces(text)
    text = convert_to_circumflex(text)

    # 3) %囲みの保護
    replacements_intact = create_replacements_list_for_intact_parts(
        text, placeholders_for_skipping_replacements
    )
    # 長い順にソートして置換
    replacements_intact_sorted = sorted(replacements_intact, key=lambda x: len(x[0]), reverse=True)
    for original, ph in replacements_intact_sorted:
        text = text.replace(original, ph)

    # 4) @囲みの局所置換
    tmp_local_list = create_replacements_list_for_localized_replacement(
        text, placeholders_for_localized_replacement, replacements_list_for_localized_string
    )
    tmp_local_list_sorted = sorted(tmp_local_list, key=lambda x: len(x[0]), reverse=True)
    for original, ph, replaced_str in tmp_local_list_sorted:
        text = text.replace(original, ph)

    # 5) 大域置換
    valid_replacements = {}
    for old, new, ph in replacements_final_list:
        if old in text:
            text = text.replace(old, ph)
            valid_replacements[ph] = new

    # 6) 二文字語根の置換 (2周)
    valid_2char_1 = {}
    for old, new, ph in replacements_list_for_2char:
        if old in text:
            text = text.replace(old, ph)
            valid_2char_1[ph] = new

    valid_2char_2 = {}
    for old, new, ph in replacements_list_for_2char:
        if old in text:
            ph2 = "!"+ph+"!"
            text = text.replace(old, ph2)
            valid_2char_2[ph2] = new

    # 7) placeholder復元 (2周目→1周目→大域→局所→保護)
    for ph2, new_val in reversed(valid_2char_2.items()):
        text = text.replace(ph2, new_val)
    for ph1, new_val in reversed(valid_2char_1.items()):
        text = text.replace(ph1, new_val)
    for ph, new_val in valid_replacements.items():
        text = text.replace(ph, new_val)

    # 局所置換(@...)の復元
    for original, ph, replaced_str in tmp_local_list_sorted:
        text = text.replace(ph, replaced_str.replace("@",""))

    # 保護(%...)の復元
    for original, ph in replacements_intact_sorted:
        text = text.replace(ph, original.replace("%",""))

    # 8) HTMLが必要な場合
    if "HTML" in format_type:
        # 改行を <br> に
        text = text.replace("\n", "<br>\n")
        text = wrap_text_with_ruby(text, chunk_size=10)
        text = re.sub(r"   ", "&nbsp;&nbsp;&nbsp;", text)
        text = re.sub(r"  ", "&nbsp;&nbsp;", text)

    return text

# ================================
# 6) multiprocessing 関連
# ================================
def process_segment(
    lines: List[str],
    placeholders_for_skipping_replacements: List[str],
    replacements_list_for_localized_string: List[Tuple[str, str, str]],
    placeholders_for_localized_replacement: List[str],
    replacements_final_list: List[Tuple[str, str, str]],
    replacements_list_for_2char: List[Tuple[str, str, str]],
    format_type: str
) -> str:
    """
    文字列のリスト(lines)を結合して
    orchestrate_comprehensive_esperanto_text_replacement を呼ぶ。
    """
    segment = '\n'.join(lines)
    result = orchestrate_comprehensive_esperanto_text_replacement(
        text=segment,
        placeholders_for_skipping_replacements=placeholders_for_skipping_replacements,
        replacements_list_for_localized_string=replacements_list_for_localized_string,
        placeholders_for_localized_replacement=placeholders_for_localized_replacement,
        replacements_final_list=replacements_final_list,
        replacements_list_for_2char=replacements_list_for_2char,
        format_type=format_type
    )
    return result

def parallel_process(
    text: str,
    num_processes: int,
    placeholders_for_skipping_replacements: List[str],
    replacements_list_for_localized_string: List[Tuple[str, str, str]],
    placeholders_for_localized_replacement: List[str],
    replacements_final_list: List[Tuple[str, str, str]],
    replacements_list_for_2char: List[Tuple[str, str, str]],
    format_type: str
) -> str:
    """
    与えられた text を行単位で分割し、
    process_segment をマルチプロセスで並列実行した結果を結合。
    """
    lines = text.split('\n')
    num_lines = len(lines)
    if num_processes < 1:
        num_processes = 1
    lines_per_process = max(num_lines // num_processes, 1)

    ranges = [(i * lines_per_process, (i + 1) * lines_per_process) for i in range(num_processes)]
    # 最後に残り全部を割り当て
    ranges[-1] = (ranges[-1][0], num_lines)

    with multiprocessing.Pool(processes=num_processes) as pool:
        results = pool.starmap(
            process_segment,
            [
                (
                    lines[start:end],
                    placeholders_for_skipping_replacements,
                    replacements_list_for_localized_string,
                    placeholders_for_localized_replacement,
                    replacements_final_list,
                    replacements_list_for_2char,
                    format_type
                )
                for (start, end) in ranges
            ]
        )

    return '\n'.join(results)
