"""Constructor failure must not leak a live SQLite connection."""
import sqlite3
import unittest
from unittest.mock import Mock, patch

from fanout_engine.ledger import Ledger


class LedgerInitializationCleanupTests(unittest.TestCase):
    def test_failed_foreign_key_pragma_closes_connection(self) -> None:
        db = Mock()
        db.execute.side_effect = sqlite3.OperationalError("synthetic pragma failure")
        with patch("fanout_engine.ledger.sqlite3.connect", return_value=db):
            with self.assertRaisesRegex(sqlite3.OperationalError, "pragma failure"):
                Ledger()
        db.close.assert_called_once_with()
        db.executescript.assert_not_called()

    def test_failed_schema_initialization_closes_connection(self) -> None:
        db = Mock()
        db.executescript.side_effect = sqlite3.OperationalError("synthetic schema failure")
        with patch("fanout_engine.ledger.sqlite3.connect", return_value=db):
            with self.assertRaisesRegex(sqlite3.OperationalError, "schema failure"):
                Ledger()
        db.execute.assert_called_once_with("PRAGMA foreign_keys=ON")
        db.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
