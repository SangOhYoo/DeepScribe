import os
import re
import csv
import logging
from collections import deque
from typing import List, Dict, Any, Tuple, Optional

logger = logging.getLogger("NovelTranslator.Onomatopoeia")

# ─── Pure-Python Aho-Corasick Algorithm ───────────────────────────────────

class AhoCorasick:
    def __init__(self):
        self.trie = [{}]  # List of state transitions: dict of char -> state_idx
        self.fail = [0]
        self.output = [[]]  # List of matched pattern indices for each state
        self.patterns = []

    def add_pattern(self, pattern: str, idx: int):
        node = 0
        for char in pattern:
            if char not in self.trie[node]:
                self.trie[node][char] = len(self.trie)
                self.trie.append({})
                self.fail.append(0)
                self.output.append([])
            node = self.trie[node][char]
        self.output[node].append(idx)
        self.patterns.append(pattern)

    def build(self):
        queue = deque()
        # Level 1 fail states point to root (0)
        for char, child in self.trie[0].items():
            self.fail[child] = 0
            queue.append(child)

        while queue:
            node = queue.popleft()
            for char, child in self.trie[node].items():
                fail_state = self.fail[node]
                while fail_state > 0 and char not in self.trie[fail_state]:
                    fail_state = self.fail[fail_state]
                
                if char in self.trie[fail_state]:
                    self.fail[child] = self.trie[fail_state][char]
                else:
                    self.fail[child] = 0
                
                # Merge outputs from fail state
                self.output[child].extend(self.output[self.fail[child]])
                queue.append(child)

    def search(self, text: str) -> List[Tuple[int, int, str]]:
        """
        Search for all patterns in text.
        Returns a list of tuples: (start_idx, end_idx, pattern_string)
        """
        results = []
        node = 0
        for i, char in enumerate(text):
            while node > 0 and char not in self.trie[node]:
                node = self.fail[node]
            if char in self.trie[node]:
                node = self.trie[node][char]
            else:
                node = 0
            
            for pattern_idx in self.output[node]:
                pattern = self.patterns[pattern_idx]
                results.append((i - len(pattern) + 1, i + 1, pattern))
        return results


# ─── Heuristic Kana Extractor ─────────────────────────────────────────────

JAPANESE_KANA_PAT = re.compile(r'^[\u3040-\u309f\u30a0-\u30ff\u30fc\u30c3\u3063]+$')

def is_all_kana(text: str) -> bool:
    """Check if the text consists entirely of Hiragana/Katakana (including small tsu/long vowels)."""
    return bool(JAPANESE_KANA_PAT.match(text))


def extract_mecab(text: str) -> List[str]:
    """Extract adverbs/interjections consisting of Kana using MeCab if installed."""
    found = []
    try:
        import MeCab
        tagger = MeCab.Tagger()
        node = tagger.parseToNode(text)
        while node:
            features = node.feature.split(',')
            pos = features[0]
            surface = node.surface
            # Adverb (副詞) or Interjection (感動詞) containing only kana of length >= 2
            if pos in ('副詞', '感動詞') and is_all_kana(surface) and len(surface) >= 2:
                found.append(surface)
            node = node.next
    except Exception:
        pass
    return found


def extract_sudachi(text: str) -> List[str]:
    """Extract adverbs/interjections consisting of Kana using SudachiPy if installed."""
    found = []
    try:
        from sudachipy import dictionary
        tokenizer = dictionary.Dictionary().create()
        mode = tokenizer.SplitMode.C
        tokens = tokenizer.tokenize(text, mode)
        for token in tokens:
            pos = token.part_of_speech()[0]
            surface = token.surface()
            if pos in ('副詞', '感動詞') and is_all_kana(surface) and len(surface) >= 2:
                found.append(surface)
    except Exception:
        pass
    return found


def extract_regex(text: str) -> List[str]:
    """
    Extract unregistered onomatopoeia candidate structures using strict pattern matches.
    - Katakana ABAB structure (2-3 Katakana repeated, e.g. クチュクチュ)
    - Katakana AッBリ structure (1 Katakana + small tsu + 1 Katakana + ri, e.g. ネットリ)
    - Katakana ending with っと / ット / んと / ント / と / ト (e.g. ドキッと, ピクンと, ゴクリと)
    """
    found = []

    # 1. Katakana ABAB structure (2-3 Katakana/vowel repeated)
    p1 = re.compile(r'([\u30a0-\u30ff\u30fc]{2,3})\1')
    for m in p1.finditer(text):
        found.append(m.group(0))

    # 2. Katakana AッBリ / AッBリ structure
    p2 = re.compile(r'([\u30a0-\u30ff])[ッ]([\u30a0-\u30ff])[リ]')
    for m in p2.finditer(text):
        found.append(m.group(0))

    # 3. Katakana ending with っと / ット / んと / ント (with small tsu or n)
    # e.g. ドキッと, ピクンと, ハッと, グッと, ビクッと, ット
    # Stop words list to filter out common grammar, pronouns, and loanword nouns
    STOP_WORDS = {
        # Common grammar / adverbs / pronouns
        "こと", "もの", "ひと", "ため", "とき", "から", "까지", "까지는", "까지도", "까지와",
        "まで", "ほう", "よう", "そう", "これ", "あれ", "それ", "どれ", "ここ", "そこ", "あそこ", "どこ",
        "もっと", "ずっと", "きっと", "やっと", "ちょっと", "おっと", "さっと", "ちっと",
        "ゆっくり", "はっきり", "やっぱり", "ぴったり", "すっきり", "しっかり", 
        "うっかり", "さっぱり", "たっぷり", "めっきり", "そっくり", "がっかり",
        "ばっぱり", "ぴったりと", "ゆっくりと", "하키리와", "역시와", "あったり", "いったり", "하거나", "하거나와", "したり", "だったり", "의거", "의거하여", "のっとり",
        "ほんと", "ほんとに", "まったく", "まったくと", "ますます", "まだまだ", 
        "もしもし", "もともと", "せいぜい", "ときどき", "しばしば", "それぞれ",
        "なんと", "なんとなく", "どうと", "いいと", "いいこと", "いいもの",
        # Common Katakana nouns / loanwords
        "スカート", "ウエスト", "シャフト", "ズボン", "ベッド", "ケット", "シャツ",
        "テスト", "コート", "シート", "ルート", "ノート", "ゲート",
        "キャスト", "ラスト", "イラスト", "コスト", "ポスト", "ベスト",
        "ホスト", "ゲスト", "ペニス", "アヌス", "クリトリス", "クンニ", "フェラ",
        "セックス", "コンドーム", "ローター", "바이브", "シーツ", "シャワー",
        "クローゼット", "カーペット", "ストレート", "ジャケット", "ポケット",
        "ブラウス", "ドレス", "ソックス", "ショーツ", "パンツ", "ベルト",
        "フロント", "アパート", "マンション", "パート", "リポート", "レポート",
        "サポート", "スマート", "スタート", "ターゲット", "マーケット", "チケット",
        "ヘルメット", "ラケット", "タバコ", "チョコレート", "ヨーグルト", "ポテト",
        "ピストル", "テイスト", "アーティスト", "フェラ치스트", "오타드", "オタード", "レオタード",
        "オルガズム", "ガズム", "ケース", "소파", "ソファ", "존", "ジョン", "린다", "リンダ", "와이프", "ワイフ",
        "マイスト", "마스트", "マスト", "ウォント", "カント", "キャット", "カット", "ドット",
        "ネット", "ホット", "ヒット", "フィット", "ペット", "ウェット", "リミット", "メリット", "デメリット",
        "コミット", "サミット", "バケット", "コント", "フォント", "마운트", "マウント", "카운트", "カウント",
        "포인트", "ポイント", "프린트", "プリント", "페인트", "ペイント", "플레이트", "プレート",
        "데이트", "이스트", "로그인", "로그아웃", "레벨", "아이템", "스킬", "퀘스트", "캐릭터",
        "コケシ", "カレー", "ベッド", "ベット", "セット",
    }

    # Clean results (filter length >= 2, all kana, and not in STOP_WORDS)
    cleaned = []
    for item in found:
        word = item.strip()
        # Exclude if it contains middle dot or spaces/punctuation
        if "・" in word or " " in word or "\u3000" in word:
            continue
            
        # If the word starts with a common particle and ends in と/ト, strip the leading particle
        if len(word) > 3 and word.endswith(("と", "ト")) and word[0] in "はがをにのでへもとやてただ":
            word = word[1:]
            
        # Check if the base word (without trailing と/ト) is in STOP_WORDS or word itself is in STOP_WORDS
        base_word = word
        if base_word.endswith(("と", "ト")):
            base_word = base_word[:-1]
            
        if base_word in STOP_WORDS or word in STOP_WORDS:
            continue
            
        if len(word) >= 2 and is_all_kana(word):
            cleaned.append(word)

    return list(set(cleaned))

# ─── Onomatopoeia Dictionary & Search Coordinator ────────────────────────

class OnomatopoeiaExtractor:
    def __init__(self, main_csv_path: str):
        self.main_csv_path = main_csv_path
        self.ac = AhoCorasick()
        self.known_entries: Dict[str, Dict[str, str]] = {}
        self.load_dictionary()

    def load_dictionary(self):
        """Load registered onomatopoeia dictionary from CSV."""
        self.ac = AhoCorasick()
        self.known_entries = {}
        
        # Ensure file exists
        if not os.path.exists(self.main_csv_path):
            os.makedirs(os.path.dirname(self.main_csv_path), exist_ok=True)
            with open(self.main_csv_path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["source", "target", "category", "notes", "example_source", "example_wrong", "example_correct"])
            
            # Write a default test entry (クチュクチュ)
            with open(self.main_csv_path, "a", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "クチュクチュ", "질척질척", "의성어",
                    "상황에 따라 '질척질척', '챠박챠박' 등 젖은 마찰음 계열로 문맥에 맞게 조사(이/가, 을/를)를 붙여 자연스럽게 소설적으로 의역해야 한다. 기계적으로 '쿠츄쿠츄'라고 직역하지 마라.",
                    "部屋にクチュクチュと淫らな音が響く。",
                    "방에 쿠츄쿠츄하고 음란한 소리가 울린다.",
                    "방 안에 질척이는 음란한 소리가 울려 퍼졌다."
                ])

        try:
            content = None
            for encoding in ["utf-8-sig", "utf-8", "cp949", "shift_jis", "euc-kr"]:
                try:
                    with open(self.main_csv_path, "r", encoding=encoding) as f:
                        content = f.read()
                    break
                except Exception:
                    continue

            if not content:
                logger.error(f"Failed to read file contents of {self.main_csv_path}")
                return

            reader = csv.reader(content.splitlines())
            count = 0
            has_duplicates = False
            unique_rows = []
            seen_sources = set()
            header = None

            for row_num, row in enumerate(reader, 1):
                if not row or len(row) < 2:
                    continue
                if row_num == 1 and row[0].lower() in ("source", "원문", "원어", "소스"):
                    header = row
                    continue

                source = row[0].strip()
                if not source:
                    continue

                if source in seen_sources:
                    has_duplicates = True
                    continue

                seen_sources.add(source)
                unique_rows.append(row)

                target = row[1].strip()
                category = row[2].strip() if len(row) > 2 else "의성어"
                notes = row[3].strip() if len(row) > 3 else ""
                example_source = row[4].strip() if len(row) > 4 else ""
                example_wrong = row[5].strip() if len(row) > 5 else ""
                example_correct = row[6].strip() if len(row) > 6 else ""

                self.known_entries[source] = {
                    "source": source,
                    "target": target,
                    "category": category,
                    "notes": notes,
                    "example_source": example_source,
                    "example_wrong": example_wrong,
                    "example_correct": example_correct,
                }
                self.ac.add_pattern(source, count)
                count += 1

            self.ac.build()
            logger.info(f"Loaded {len(self.known_entries)} onomatopoeia entries into Aho-Corasick tree.")

            # Rewrite CSV to clean it up if duplicates were found
            if has_duplicates:
                logger.info("Duplicates detected in CSV dictionary. Cleaning up and rewriting CSV file...")
                try:
                    with open(self.main_csv_path, "w", encoding="utf-8-sig", newline="") as f:
                        writer = csv.writer(f)
                        if header:
                            writer.writerow(header)
                        else:
                            writer.writerow(["source", "target", "category", "notes", "example_source", "example_wrong", "example_correct"])
                        writer.writerows(unique_rows)
                except Exception as we:
                    logger.error(f"Failed to rewrite cleaned onomatopoeia CSV: {we}")

        except Exception as e:
            logger.error(f"Error loading onomatopoeia CSV: {e}")

    def extract_registered(self, text: str) -> List[Dict[str, str]]:
        """
        Find registered terms in text using Aho-Corasick tree.
        Returns list of entry dicts.
        """
        if not self.known_entries:
            return []
        matches = self.ac.search(text)
        unique_words = set(pattern for _, _, pattern in matches)
        
        results = []
        for word in unique_words:
            if word in self.known_entries:
                results.append(self.known_entries[word])
        return results

    def extract_unregistered(self, text: str) -> List[str]:
        """
        Extract unregistered candidates in text using MeCab/Sudachi and regex.
        Returns list of raw word strings.
        """
        candidates = []
        candidates.extend(extract_mecab(text))
        candidates.extend(extract_sudachi(text))
        candidates.extend(extract_regex(text))

        unregistered = []
        for cand in set(candidates):
            if cand not in self.known_entries and len(cand) >= 2:
                unregistered.append(cand)
        return sorted(unregistered)

    def format_few_shot_prompt(self, matched_entries: List[Dict[str, str]]) -> str:
        """
        Format matching entries for prompt injection.
        """
        if not matched_entries:
            return ""

        guide_lines = ["[특수 어휘 번역 가이드]"]
        example_lines = ["[번역 예시]"]

        has_guides = False
        has_examples = False

        for entry in matched_entries:
            source = entry["source"]
            target = entry["target"]
            notes = entry["notes"]
            ex_src = entry["example_source"]
            ex_wrg = entry["example_wrong"]
            ex_cor = entry["example_correct"]

            # Guide
            guide_text = ""
            if notes:
                guide_text = notes
            elif target:
                guide_text = f"상황에 따라 '{target}' 등으로 문맥에 맞게 조사(이/가, 을/를)를 붙여 자연스럽게 소설적으로 의역해야 한다. 기계적으로 직역하지 마라."

            if guide_text:
                guide_lines.append(f"- 원문에 '{source}'가 등장할 경우, {guide_text}")
                has_guides = True

            # Example
            if ex_src:
                wrong_str = ex_wrg if ex_wrg else f"{ex_src} (직역)"
                correct_str = ex_cor if ex_cor else f"{ex_src} (의역)"
                example_block = (
                    f"원문: {ex_src}\n"
                    f"오답: {wrong_str} (X)\n"
                    f"정답: {correct_str} (O)"
                )
                example_lines.append(example_block)
                example_lines.append("")  # Empty line between examples
                has_examples = True

        sections = []
        if has_guides:
            sections.append("\n".join(guide_lines))
        if has_examples:
            examples_str = "\n".join(example_lines).strip()
            sections.append(examples_str)

        return "\n\n".join(sections)
