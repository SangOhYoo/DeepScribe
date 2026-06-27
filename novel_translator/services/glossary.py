"""
Glossary Manager for Novel Translation.
Maintains a dictionary of proper nouns and terms to ensure
translation consistency across the entire novel.

Supported formats:
- CSV: source_term,target_term (one pair per line)
- JSON: {"entries": [{"source": "...", "target": "..."}, ...]}
"""

import csv
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("NovelTranslator.Glossary")


@dataclass
class GlossaryEntry:
    """A single glossary term mapping."""
    source: str
    target: str
    category: str = ""  # e.g., "character", "location", "term", "의성어"
    notes: str = ""
    example_source: str = ""
    example_wrong: str = ""
    example_correct: str = ""


class GlossaryManager:
    """
    Manages a glossary of terms for consistent novel translation.
    Provides prompt injection formatting and term lookup.
    """

    def __init__(self) -> None:
        self.entries: list[GlossaryEntry] = []
        self._source_index: dict[str, GlossaryEntry] = {}

    @property
    def size(self) -> int:
        return len(self.entries)

    def clear(self) -> None:
        """Remove all glossary entries."""
        self.entries.clear()
        self._source_index.clear()

    def add_entry(self, source: str, target: str,
                  category: str = "", notes: str = "",
                  example_source: str = "", example_wrong: str = "",
                  example_correct: str = "") -> None:
        """Add a single glossary entry."""
        source_clean = source.strip()
        if source_clean in self._source_index:
            logger.debug(f"Glossary entry for '{source_clean}' already exists. Skipping.")
            return

        entry = GlossaryEntry(
            source=source_clean,
            target=target.strip(),
            category=category.strip(),
            notes=notes.strip(),
            example_source=example_source.strip(),
            example_wrong=example_wrong.strip(),
            example_correct=example_correct.strip()
        )
        self.entries.append(entry)
        self._source_index[entry.source] = entry
        logger.debug(f"Added glossary entry: {entry.source} → {entry.target}")

    def load_from_csv(self, file_path: str) -> int:
        """
        Load glossary from a CSV file.
        Expected columns: source, target [, category, notes]
        Returns the number of entries loaded.
        """
        count = 0
        try:
            # Try UTF-8 first, then fall back to other encodings
            content = None
            for encoding in ["utf-8-sig", "utf-8", "cp949", "shift_jis", "euc-kr"]:
                try:
                    with open(file_path, "r", encoding=encoding) as f:
                        content = f.read()
                    break
                except (UnicodeDecodeError, LookupError):
                    continue

            if content is None:
                logger.error(f"Could not decode CSV file: {file_path}")
                return 0

            reader = csv.reader(content.splitlines())
            for row_num, row in enumerate(reader, 1):
                if not row or len(row) < 2:
                    continue
                # Skip header row if detected
                if row_num == 1 and row[0].lower() in ("source", "원문", "원어", "소스"):
                    continue

                source = row[0].strip()
                target = row[1].strip()
                category = row[2].strip() if len(row) > 2 else ""
                notes = row[3].strip() if len(row) > 3 else ""
                example_source = row[4].strip() if len(row) > 4 else ""
                example_wrong = row[5].strip() if len(row) > 5 else ""
                example_correct = row[6].strip() if len(row) > 6 else ""

                if source and target:
                    self.add_entry(
                        source, target, category, notes,
                        example_source, example_wrong, example_correct
                    )
                    count += 1

        except Exception as e:
            logger.error(f"Failed to load CSV glossary from {file_path}: {e}")

        logger.info(f"Loaded {count} glossary entries from CSV.")
        return count

    def load_from_json(self, file_path: str) -> int:
        """
        Load glossary from a JSON file.
        Expected format: {"entries": [{"source": "...", "target": "...", ...}, ...]}
        Returns the number of entries loaded.
        """
        count = 0
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            entries_data = data if isinstance(data, list) else data.get("entries", [])

            for item in entries_data:
                if isinstance(item, dict):
                    source = item.get("source", "").strip()
                    target = item.get("target", "").strip()
                    if source and target:
                        self.add_entry(
                            source, target,
                            item.get("category", ""),
                            item.get("notes", ""),
                            item.get("example_source", ""),
                            item.get("example_wrong", ""),
                            item.get("example_correct", "")
                        )
                        count += 1

        except Exception as e:
            logger.error(f"Failed to load JSON glossary from {file_path}: {e}")

        logger.info(f"Loaded {count} glossary entries from JSON.")
        return count

    def load_from_file(self, file_path: str) -> int:
        """Auto-detect file format and load glossary."""
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".json":
            return self.load_from_json(file_path)
        else:
            # Default to CSV for .csv, .txt, and other extensions
            return self.load_from_csv(file_path)

    def lookup(self, source_term: str) -> Optional[str]:
        """Look up a source term and return the target translation."""
        entry = self._source_index.get(source_term)
        return entry.target if entry else None

    def find_terms_in_text(self, text: str) -> list[GlossaryEntry]:
        """Find all glossary terms that appear in the given text."""
        found = []
        for entry in self.entries:
            if entry.source in text:
                found.append(entry)
        return found

    def format_for_prompt(self, relevant_text: str = "") -> str:
        """
        Format the glossary entries for injection into an LLM prompt.
        If relevant_text is provided, only includes terms found in that text.
        Excludes few-shot entries (onomatopoeia, etc.) as they are handled separately.
        """
        if not self.entries:
            return ""

        if relevant_text:
            relevant_entries = self.find_terms_in_text(relevant_text)
        else:
            relevant_entries = self.entries

        # Exclude few-shot/onomatopoeia entries from standard glossary
        normal_entries = []
        for entry in relevant_entries:
            is_few_shot = (
                entry.category.strip() in ("의성어", "onomatopoeia", "few-shot", "few_shot")
                or bool(entry.example_source or entry.example_wrong or entry.example_correct)
            )
            if not is_few_shot:
                normal_entries.append(entry)

        if not normal_entries:
            return ""

        lines = ["[용어 사전 / Glossary]"]
        lines.append("아래 용어는 반드시 지정된 번역어를 사용하십시오:")
        lines.append("")

        for entry in normal_entries:
            line = f"  • {entry.source} → {entry.target}"
            if entry.category:
                line += f" ({entry.category})"
            lines.append(line)

        return "\n".join(lines)

    def find_few_shot_entries(self, text: str) -> list[GlossaryEntry]:
        """Find all glossary entries suitable for few-shot prompting in the given text."""
        found = []
        for entry in self.entries:
            is_onomatopoeia = entry.category.strip() in ("의성어", "onomatopoeia", "few-shot", "few_shot")
            has_examples = bool(entry.example_source or entry.example_wrong or entry.example_correct)
            if entry.source in text and (is_onomatopoeia or has_examples):
                found.append(entry)
        return found

    def format_few_shot_for_prompt(self, relevant_text: str = "") -> str:
        """
        Format the few-shot / onomatopoeia guide and examples for prompt injection.
        """
        if not self.entries:
            return ""

        if relevant_text:
            few_shot_entries = self.find_few_shot_entries(relevant_text)
        else:
            few_shot_entries = [
                e for e in self.entries
                if e.category.strip() in ("의성어", "onomatopoeia", "few-shot", "few_shot")
                or bool(e.example_source or e.example_wrong or e.example_correct)
            ]

        if not few_shot_entries:
            return ""

        guide_lines = ["[특수 어휘 번역 가이드]"]
        example_lines = ["[번역 예시]"]
        
        has_guides = False
        has_examples = False

        for entry in few_shot_entries:
            # Build Guide using notes or fallback description
            guide_text = ""
            if entry.notes:
                guide_text = entry.notes
            elif entry.target:
                guide_text = f"상황에 따라 '{entry.target}' 등으로 문맥에 맞게 조사(이/가, 을/를)를 붙여 자연스럽게 소설적으로 의역해야 한다. 기계적으로 직역하지 마라."

            if guide_text:
                guide_lines.append(f"- 원문에 '{entry.source}'가 등장할 경우, {guide_text}")
                has_guides = True

            # Build Example
            if entry.example_source:
                wrong_str = entry.example_wrong if entry.example_wrong else f"{entry.example_source} (직역)"
                correct_str = entry.example_correct if entry.example_correct else f"{entry.example_source} (의역)"
                example_block = (
                    f"원문: {entry.example_source}\n"
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
            # Strip trailing empty lines from examples
            examples_str = "\n".join(example_lines).strip()
            sections.append(examples_str)

        return "\n\n".join(sections)

    def export_to_csv(self, file_path: str) -> None:
        """Export current glossary to a CSV file."""
        try:
            with open(file_path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["source", "target", "category", "notes", "example_source", "example_wrong", "example_correct"])
                for entry in self.entries:
                    writer.writerow([
                        entry.source, entry.target,
                        entry.category, entry.notes,
                        entry.example_source, entry.example_wrong, entry.example_correct
                    ])
            logger.info(f"Exported {len(self.entries)} glossary entries to {file_path}")
        except Exception as e:
            logger.error(f"Failed to export glossary to {file_path}: {e}")
