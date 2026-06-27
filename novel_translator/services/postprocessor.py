"""
Post-processor for translated novel text.
Merges chunks, cleans artifacts, normalizes formatting.
"""

import logging
import os
import re
from typing import Optional

logger = logging.getLogger("NovelTranslator.PostProcessor")


class PostProcessor:
    """Cleans and merges translated text chunks into a final document."""

    # Patterns to clean from LLM output
    CLEANUP_PATTERNS = [
        # Remove "Translating..." or "번역 중..." markers (often outputted when thinking is skipped/forced)
        (re.compile(r'^\s*\[?(?:Translating|번역\s*중)(?:\.+|\]|\s*$)\s*\n?', re.IGNORECASE | re.MULTILINE), ''),
        # Remove "Translation:" or "번역:" prefixes
        (re.compile(r'^(?:번역|Translation|Translated|번역문|翻訳)[:\s：]*', re.MULTILINE), ''),
        # Remove markdown code block wrappers
        (re.compile(r'^```[a-z]*\s*\n?', re.MULTILINE), ''),
        (re.compile(r'\n?```\s*$', re.MULTILINE), ''),
        # Remove excessive blank lines (3+ → 2)
        (re.compile(r'\n{4,}'), '\n\n\n'),
        # Remove trailing whitespace per line
        (re.compile(r'[ \t]+$', re.MULTILINE), ''),
    ]

    def clean_repetitions(self, text: str) -> str:
        """Collapses runaway token repetitions and line repetitions."""
        if not text:
            return ""

        # 1. Collapse within-line repetition of patterns (e.g. "아" repeating 10+ times, or "!?" repeating 10+ times)
        # We restrict the repeating unit length to 1-6 characters to avoid false matches on longer phrases,
        # and collapse to 5 repetitions.
        def collapse_match(match):
            unit = match.group(1)
            if not unit.strip():  # Skip whitespace-only units (spaces, tabs, etc.)
                return match.group(0)
            return unit * 5

        # Pattern matches a group of 1 to 6 chars, followed by that same group 9 or more times (total 10+ times)
        text = re.sub(r'(.{1,6})\1{9,}', collapse_match, text)

        # 2. Collapse consecutive duplicate lines (repeating 3+ times) down to 2 repetitions.
        text = re.sub(r'(^.+$\n?)\1{2,}', r'\1\1', text, flags=re.MULTILINE)

        return text

    def clean_chunk(self, text: str) -> str:
        """Clean a single translated chunk."""
        if not text:
            return ""
        result = text.strip()
        for pattern, replacement in self.CLEANUP_PATTERNS:
            result = pattern.sub(replacement, result)
        result = self.clean_repetitions(result)
        return result.strip()

    def merge_chunks(self, translated_chunks: list[str]) -> str:
        """
        Merge translated chunks into a single coherent document.
        Handles paragraph boundaries between chunks.
        """
        if not translated_chunks:
            return ""

        cleaned = [self.clean_chunk(c) for c in translated_chunks if c]
        if not cleaned:
            return ""

        # Join with double newline (paragraph separator)
        merged = "\n\n".join(cleaned)

        # Final cleanup pass
        # Remove duplicate paragraph separators at chunk boundaries
        merged = re.sub(r'\n{4,}', '\n\n\n', merged)
        
        # Collapse any repetition issues that span across chunk boundaries
        merged = self.clean_repetitions(merged)

        # Unify character names
        merged = self.unify_names(merged)

        return merged.strip()

    def unify_names(self, text: str) -> str:
        """
        Detects and resolves inconsistent character name translations.
        E.g., if '仁美' is translated as both '히토미(仁美)' and '마유미(仁美)' in the same text,
        it unifies them to the correct or most frequent translation.
        Also unifies standalone references to the character.
        """
        if not text:
            return ""

        # Common Japanese name Kanji to Korean reading mapping for validation/override
        COMMON_NAME_READINGS = {
            "仁美": "히토미",
            "真弓": "마유미",
            "雅美": "마유미",
            "美香": "미카",
            "陽子": "요코",
            "裕子": "유코",
            "結衣": "유이",
            "美咲": "미사키",
            "愛美": "마나미",
            "春香": "하루카",
            "沙織": "사오리",
            "香織": "카오리",
            "千尋": "치히로",
            "麻衣": "마이",
            "直美": "나오미",
            "奈々": "나나",
            "菜々子": "나나코",
            "莉子": "리코",
            "葵": "아오이",
            "健太": "켄타",
            "翔太": "쇼타",
            "拓海": "타쿠미",
            "大輔": "다이스케",
            "翔": "쇼",
            "蓮": "렌",
            "颯太": "소타",
            "悠真": "유마",
            "陽翔": "하루토",
            "湊": "미나토",
            "陸": "리쿠",
        }

        import re
        from collections import defaultdict

        # Find all occurrences of "한글(한자)"
        # CJK ideographs range: \u4e00-\u9fff, \u3400-\u4dbf, \uf900-\ufaff
        pattern = re.compile(r'([가-힣]{2,10})\s*\(([\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]{1,10})\)')
        matches = pattern.findall(text)

        if not matches:
            return text

        # Map each kanji to its translated Korean names and their counts
        kanji_to_names = defaultdict(lambda: defaultdict(int))
        for kr_name, kanji in matches:
            kanji_to_names[kanji][kr_name] += 1

        # Track which Korean names are mapped to multiple Kanji to avoid incorrect merges
        name_to_kanjis = defaultdict(set)
        for kanji, kr_names in kanji_to_names.items():
            for kr_name in kr_names:
                name_to_kanjis[kr_name].add(kanji)

        replacements = {}
        standalone_replacements = {}

        for kanji, kr_names in kanji_to_names.items():
            current_names = list(kr_names.keys())
            
            # We want to unify if there are multiple translations OR if the name is in COMMON_NAME_READINGS and is incorrect
            correct_reading = COMMON_NAME_READINGS.get(kanji)
            
            # Case 1: Multiple different translations in the same text
            # Case 2: Consistently wrong translation (e.g. only 1 name, but it doesn't match the dictionary)
            has_inconsistency = len(kr_names) > 1
            has_dictionary_mismatch = (correct_reading and 
                                       len(kr_names) == 1 and 
                                       current_names[0] != correct_reading and
                                       kanji not in name_to_kanjis[correct_reading] and 
                                       len(name_to_kanjis[correct_reading]) == 0)

            if not (has_inconsistency or has_dictionary_mismatch):
                continue

            # Decide the target (correct) Korean name
            if correct_reading and (correct_reading in kr_names or has_dictionary_mismatch):
                target_name = correct_reading
            else:
                # Fallback to the most frequent one
                target_name = max(kr_names, key=kr_names.get)

            # Mark all incorrect variants for replacement
            all_variants = current_names if has_inconsistency else [current_names[0]]
            for kr_name in all_variants:
                if kr_name == target_name:
                    continue

                # Add parenthesized replacement
                old_pat = f"{kr_name}({kanji})"
                new_pat = f"{target_name}({kanji})"
                replacements[old_pat] = new_pat
                
                # Check if we can safely replace standalone names
                # Only if the incorrect name is not mapped to any other Kanji in the text
                if len(name_to_kanjis[kr_name]) <= 1:
                    standalone_replacements[kr_name] = target_name

        # Apply parenthesized replacements first
        for old_pat, new_pat in replacements.items():
            escaped_old = re.escape(old_pat)
            text = re.sub(escaped_old, new_pat, text)

        # Apply standalone replacements with word/character boundary checks
        particles = "씨|은|는|이|가|을|를|의|에게|한테|와|과|께|에서|고|라고|이랑|며|이며|이자|라|이라|님|들|만|뿐|도|조차|마저|까지|부터"
        for old_name, new_name in standalone_replacements.items():
            pattern_str = rf'(?<![가-힣]){old_name}(?=(?:{particles})?(?![가-힣]))'
            text = re.sub(pattern_str, new_name, text)

        return text


    def save_to_file(
        self, text: str, original_path: str, output_dir: Optional[str] = None
    ) -> str:
        """
        Save translated text to a file.
        Output filename: [original_name]_translated.txt

        Returns the saved file path.
        """
        base_name = os.path.splitext(os.path.basename(original_path))[0]
        output_name = f"{base_name}_translated.txt"

        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, output_name)
        else:
            output_path = os.path.join(os.path.dirname(original_path), output_name)

        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(text)
            logger.info(f"Saved translated file: {output_path}")
            return output_path
        except OSError as e:
            logger.error(f"Failed to save translation: {e}")
            raise
