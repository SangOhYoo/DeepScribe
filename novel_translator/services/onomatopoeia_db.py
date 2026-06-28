import sqlite3
import os
import logging
from typing import List, Dict, Any

logger = logging.getLogger("NovelTranslator.OnomatopoeiaDB")

class OnomatopoeiaDB:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pending_words (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    word TEXT UNIQUE,
                    context TEXT,
                    suggested_translation TEXT,
                    notes TEXT,
                    example_source TEXT,
                    example_wrong TEXT,
                    example_correct TEXT,
                    status TEXT DEFAULT 'pending_extraction', -- pending_extraction, pending_review, approved, rejected
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # status 컬럼에 인덱스를 추가하여 'pending_extraction', 'pending_review' 상태의 단어를 빠르게 조회합니다.
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_pending_words_status ON pending_words (status);
            """)
            conn.commit()
            conn.close()
            logger.info(f"Initialized SQLite database at {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize onomatopoeia DB: {e}")

    def add_to_queue(self, word: str, context: str):
        """Add a newly found unregistered word to the queue."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            # If word already exists, we ignore to prevent duplicates
            cursor.execute("""
                INSERT OR IGNORE INTO pending_words (word, context, example_source, status) 
                VALUES (?, ?, ?, 'pending_extraction')
            """, (word.strip(), context.strip(), context.strip()))
            conn.commit()
            conn.close()
            logger.info(f"Added word '{word}' to pending_extraction queue.")
        except Exception as e:
            logger.error(f"Error adding word '{word}' to queue: {e}")

    def get_pending_extraction(self) -> List[Dict[str, Any]]:
        """Fetch all entries waiting for LLM worker."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM pending_words WHERE status = 'pending_extraction'")
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting pending extraction: {e}")
            return []

    def update_llm_result(self, word: str, translation: str, notes: str, wrong: str, correct: str):
        """Update entry with LLM generated data and set status to pending_review."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE pending_words 
                SET suggested_translation = ?, notes = ?, example_wrong = ?, example_correct = ?, status = 'pending_review'
                WHERE word = ?
            """, (translation.strip(), notes.strip(), wrong.strip(), correct.strip(), word))
            conn.commit()
            conn.close()
            logger.info(f"Updated word '{word}' with LLM generated values.")
        except Exception as e:
            logger.error(f"Error updating LLM result for '{word}': {e}")

    def get_pending_review(self) -> List[Dict[str, Any]]:
        """Fetch all entries waiting for admin review."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM pending_words WHERE status = 'pending_review' ORDER BY created_at DESC")
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting pending review: {e}")
            return []

    def set_status(self, word: str, status: str):
        """Update status of a word."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("UPDATE pending_words SET status = ? WHERE word = ?", (status, word))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error setting status for '{word}': {e}")

    def delete_word(self, word: str):
        """Delete word from database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM pending_words WHERE word = ?", (word,))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error deleting word '{word}': {e}")
