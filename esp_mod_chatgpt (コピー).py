# esp_mod.py

import re
import json
from typing import List, Tuple, Dict
import multiprocessing
from bs4 import BeautifulSoup, NavigableString
from bs4.element import Tag

# =========================================
# 1) エスペラント文字関連の辞書定義
# =========================================
x_to_circumflex = {
    'cx': 'ĉ', 'gx': 'ĝ', 'hx': 'ĥ', 'jx': 'ĵ',
    'sx': 'ŝ', 'ux': 'ŭ',
    'Cx': 'Ĉ', 'Gx': 'Ĝ', 'Hx': 'Ĥ', 'Jx': 'Ĵ',
    'Sx': 'Ŝ', 'Ux': 'Ŭ'
}
circumflex_to_x = {
    'ĉ': 'cx', 'ĝ': 'gx', 'ĥ': 'hx', 'ĵ': 'jx',
    'ŝ': 'sx', 'ŭ': 'ux',
    'Ĉ': 'Cx', 'Ĝ': 'Gx', 'Ĥ': 'Hx', 'Ĵ': 'Jx',
    'Ŝ': 'Sx', 'Ŭ': 'Ux'
}
x_to_hat = {
    'cx': 'c^', 'gx': 'g^', 'hx': 'h^', 'jx': 'j^',
    'sx': 's^', 'ux': 'u^',
    'Cx': 'C^', 'Gx': 'G^', 'Hx': 'H^', 'Jx': 'J^',
    'Sx': 'S^', 'Ux': 'U^'
}
hat_to_x = {
    'c^': 'cx', 'g^': 'gx', 'h^': 'hx', 'j^': 'jx',
    's^': 'sx', 'u^': 'ux',
    'C^': 'Cx', 'G^': 'Gx', 'H^': 'Hx', 'J^': 'Jx',
    'S^': 'Sx', 'U^': 'Ux'
}
hat_to_circumflex = {
    'c^': 'ĉ', 'g^': 'ĝ', 'h^': 'ĥ', 'j^': 'ĵ',
    's^': 'ŝ', 'u^': 'ŭ',
    'C^': 'Ĉ', 'G^': 'Ĝ', 'H^': 'Ĥ', 'J^': 'Ĵ',
    'S^': 'Ŝ', 'U^': 'Ŭ'
}
circumflex_to_hat = {
    'ĉ': 'c^', 'ĝ': 'g^', 'ĥ': 'h^', 'ĵ': 'j^',
    'ŝ': 's^', 'ŭ': 'u^',
    'Ĉ': 'C^', 'Ĝ': 'G^', 'Ĥ': 'H^', 'Ĵ': 'J^',
    'Ŝ': 'S^', 'Ŭ': 'U^'
}


# =========================================
# 2) 文字変換用の補助関数
# =========================================
def replace_esperanto_chars(text: str, char_dict: Dict[str, str]) -> str:
    """与えられた辞書 char_dict を使って、text 内のキー文字列をすべて置換する。"""
    for original_char, converted_char in char_dict.items():
        text = text.replace(original_char, converted_char)
    return text

def convert_to_circumflex(text: str) -> str:
    """
    テキストを字上符形式（ĉ, ĝ, ĥ, ĵ, ŝ, ŭなど）に統一します。
    x形式(cx, gx...) や ^形式(c^, g^...) などが含まれていても、すべて ĉ などに正規化する。
    """
    # ^ 表記
    text = replace_esperanto_chars(text, hat_to_circumflex)
    # x 表記
    text = replace_esperanto_chars(text, x_to_circumflex)
    return text

def unify_halfwidth_spaces(text: str) -> str:
    """
    全角スペース(U+3000)は変更せず、半角スペースと視覚的に紛らわしい
    特殊な空白文字 (U+00A0, U+2002...200A など) を ASCII半角スペース(U+0020)に置換。
    """
    pattern = r"[\u00A0\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200A]"
    return re.sub(pattern, " ", text)


# =========================================
# 3) HTMLルビ用のラッピング関数
# =========================================
def wrap_text_with_ruby(html_string: str, chunk_size: int = 10) -> str:
    """
    BeautifulSoupを使い、<ruby>タグでかかっていないテキスト部分にも
    強制的に<ruby>を被せる。
    """
    soup = BeautifulSoup(html_string, 'lxml')

    def process_element(element: Tag, in_ruby: bool = False) -> None:
        """再帰的に子要素をたどり、<ruby>/<rt> でなければ chunk_size ごとに <ruby>タグ化。"""
        if element.name in ['ruby', 'rt']:
            in_ruby = True

        for child in list(element.children):
            if isinstance(child, NavigableString):
                text_content = str(child)
                # 空白や改行のみの場合はスキップ
                if not text_content.strip():
                    continue

                # すでにruby内ならスキップ
                if in_ruby:
                    continue

                # chunk_sizeごとに分割
                chunks = [text_content[i : i + chunk_size] for i in range(0, len(text_content), chunk_size)]
                new_tags = []
                for chunk in chunks:
                    # 半角スペースを &nbsp; に
                    chunk = chunk.replace(" ", "&nbsp;").replace("　", "&nbsp;&nbsp;")
                    ruby_tag = soup.new_tag('ruby')
                    ruby_tag.string = chunk
                    new_tags.append(ruby_tag)

                child.replace_with(*new_tags)

            elif child.name and child.name.lower() in ['script', 'style']:
                # <script>/<style>内は編集しない
                continue
            else:
                # 子要素を再帰的に処理
                process_element(child, in_ruby)

    # 実行
    process_element(soup, in_ruby=False)

    # <html> と <body> を除去
    if soup.html:
        soup.html.unwrap()
    if soup.body:
        soup.body.unwrap()

    # 先頭や末尾に自動挿入された <p> を除去 (必要なら)
    if soup.contents and soup.contents[0].name == "p":
        soup.contents[0].unwrap()
    if soup.contents and soup.contents[-1].name == "p":
        soup.contents[-1].unwrap()

    # &amp;nbsp; を &nbsp; に戻す
    final_str = str(soup).replace("&amp;nbsp;", "&nbsp;")
    return final_str


# =========================================
# 4) 占位符(placeholder)置換用の関数
# =========================================
def safe_replace(text: str, replacements: List[Tuple[str, str, str]]) -> str:
    """
    replacementsの各要素 (old, new, placeholder) について
    text内の old を placeholder に一時置換し、
    その後 placeholder を new に置換し直す。
    """
    valid_replacements = {}
    # old → placeholder
    for old, new, placeholder in replacements:
        if old in text:
            text = text.replace(old, placeholder)
            valid_replacements[placeholder] = new
    # placeholder → new
    for ph, new_val in valid_replacements.items():
        text = text.replace(ph, new_val)
    return text


# =========================================
# 5) '%'で囲まれた部分を保持するための関数群
# =========================================
PERCENT_PATTERN = re.compile(r'%(.{1,50}?)%')

def find_strings_in_text(text: str) -> List[str]:
    """
    '%foo%' の形で囲まれた部分をすべて抜き出す(50文字以内)。
    かぶりや重複は避ける。
    """
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
    '%xxx%' の部分を、そのまま置換せず保持するために
    placeholderリストと対応付けを作る ([(original, placeholder), ...])
    """
    matches = find_strings_in_text(text)
    results = []
    for i, match in enumerate(matches):
        if i < len(placeholders):
            # '%xxx%' → somePlaceholder
            results.append((f"%{match}%", placeholders[i]))
        else:
            break  # 置換用placeholderが足りない場合
    return results


# =========================================
# 6) '@'で囲まれた局所置換の関数
# =========================================
AT_PATTERN = re.compile(r'@(.{1,18}?)@')

def find_strings_in_text_for_localized_replacement(text: str) -> List[str]:
    """
    '@foo@' の形で囲まれた部分(18文字以内)を抜き出す。
    かぶりや重複は避ける。
    """
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
    '@foo@' の各 foo を、局所的に safe_replace で置換し、その置換後文字列を
    placeholderリストに置き換えておく。
    """
    matches = find_strings_in_text_for_localized_replacement(text)
    tmp_list = []
    for i, match in enumerate(matches):
        if i < len(placeholders):
            # matchを置換 (局所的に replacements_list_for_localized_string)
            replaced_match = safe_replace(match, replacements_list_for_localized_string)
            tmp_list.append([f"@{match}@", placeholders[i], replaced_match])
        else:
            break
    return tmp_list


# =========================================
# 7) メインの置換処理
# =========================================
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
    文章全体に対して、複雑な段階的置換を施す。
    1) 半角スペース正規化
    2) ĉ 等への統一
    3) '%...%' で囲まれた部分は一時保護
    4) '@...@' で囲まれた部分は局所的に置換
    5) 大域的置換
    6) 2文字語根の置換を2周
    7) placeholderを最終的に元に戻す
    8) 必要に応じてHTML整形 (wrap_text_with_rubyなど)
    """
    # 1,2) 空白の統一 & ĉ 等変換
    text = unify_halfwidth_spaces(text)
    text = convert_to_circumflex(text)

    # 3) %囲みをplaceholderに
    replacements_for_intact = create_replacements_list_for_intact_parts(
        text, placeholders_for_skipping_replacements
    )
    # 置換長が長いものから先に適用
    replacements_for_intact_sorted = sorted(replacements_for_intact, key=lambda x: len(x[0]), reverse=True)
    for original, ph in replacements_for_intact_sorted:
        text = text.replace(original, ph)

    # 4) @囲みを局所置換
    tmp_local_list = create_replacements_list_for_localized_replacement(
        text,
        placeholders_for_localized_replacement,
        replacements_list_for_localized_string
    )
    tmp_local_list_sorted = sorted(tmp_local_list, key=lambda x: len(x[0]), reverse=True)
    for original, ph, replaced_str in tmp_local_list_sorted:
        text = text.replace(original, ph)

    # 5) 大域的置換 (漢字→esperanto等)
    valid_replacements = {}
    for old, new, ph in replacements_final_list:
        if old in text:
            text = text.replace(old, ph)
            valid_replacements[ph] = new

    # 6) 2文字語根を2周
    valid_2char_1 = {}
    for old, new, ph in replacements_list_for_2char:
        if old in text:
            text = text.replace(old, ph)
            valid_2char_1[ph] = new

    valid_2char_2 = {}
    for old, new, ph in replacements_list_for_2char:
        if old in text:
            ph2 = "!" + ph + "!"
            text = text.replace(old, ph2)
            valid_2char_2[ph2] = new

    # 7) placeholderを復元
    #   2周目 → 1周目 → 大域 的な順
    for ph2, new_val in reversed(valid_2char_2.items()):
        text = text.replace(ph2, new_val)
    for ph1, new_val in reversed(valid_2char_1.items()):
        text = text.replace(ph1, new_val)
    for ph, new_val in valid_replacements.items():
        text = text.replace(ph, new_val)

    # 7-2) % / @ 部分も復元
    for original, ph, replaced_str in tmp_local_list_sorted:
        # 局所置換の@は削除して元に
        text = text.replace(ph, replaced_str.replace("@",""))
    for original, ph in replacements_for_intact_sorted:
        # 保護部分の%は削除して元に
        text = text.replace(ph, original.replace("%",""))

    # 8) HTML整形が必要な場合
    if "HTML" in format_type:
        # 改行を<br>に
        text = text.replace("\n", "<br>\n")
        text = wrap_text_with_ruby(text, chunk_size=10)
        # 半角スペース複数を &nbsp; 化
        text = re.sub(r"   ", "&nbsp;&nbsp;&nbsp;", text)
        text = re.sub(r"  ", "&nbsp;&nbsp;", text)

    return text


# =========================================
# 8) multiprocessing用の2関数
# =========================================
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
    文字列のリスト(lines)を結合し、orchestrate_comprehensive_esperanto_text_replacement を実行
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
    テキストを行単位で分割し、num_processes 個のプロセスに分散して
    process_segment を starmap で並列実行 → 結果を結合して返す。
    """
    lines = text.split('\n')
    num_lines = len(lines)
    if num_processes < 1:
        num_processes = 1
    lines_per_process = num_lines // num_processes

    # 範囲の割り当て
    ranges = []
    for i in range(num_processes):
        start_index = i * lines_per_process
        end_index = (i + 1) * lines_per_process
        ranges.append((start_index, end_index))
    # 最後のプロセスに残りをすべて割り当て
    ranges[-1] = (ranges[-1][0], num_lines)

    # プロセスプール
    with multiprocessing.Pool(processes=num_processes) as pool:
        # starmap に渡す引数: process_segment の引数順にまとめる
        # (lines[start:end], placeholders..., replacements..., format_type)
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

    # 結果を結合
    return '\n'.join(results)
