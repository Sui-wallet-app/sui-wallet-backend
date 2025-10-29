import sqlite3
from datetime import datetime
from pathlib import Path
import json
from cryptography.fernet import Fernet
import os


class DatabaseManager:
    def __init__(self, db_path="sui_wallet.db"):
        """Initialize database connection and create tables"""
        self.db_path = db_path
        self.encryption_key = self._get_or_create_encryption_key()
        self.cipher = Fernet(self.encryption_key)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _get_or_create_encryption_key(self):
        """Get or create encryption key for private keys"""
        key_file = Path(".encryption_key")
        if key_file.exists():
            with open(key_file, "rb") as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            with open(key_file, "wb") as f:
                f.write(key)
            return key

    def _create_tables(self):
        """Create necessary database tables"""
        cursor = self.conn.cursor()

        # Accounts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nickname TEXT NOT NULL,
                address TEXT UNIQUE NOT NULL,
                private_key_encrypted BLOB NOT NULL,
                scheme TEXT DEFAULT 'ed25519',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 0
            )
        """)

        # Transactions table (local cache)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                digest TEXT UNIQUE NOT NULL,
                from_address TEXT NOT NULL,
                to_address TEXT NOT NULL,
                amount REAL NOT NULL,
                status TEXT DEFAULT 'pending',
                timestamp TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Settings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        self.conn.commit()

    def _encrypt_private_key(self, private_key):
        """Encrypt private key before storing"""
        return self.cipher.encrypt(private_key.encode())

    def _decrypt_private_key(self, encrypted_key):
        """Decrypt private key when retrieving"""
        return self.cipher.decrypt(encrypted_key).decode()

    # ==================== ACCOUNT OPERATIONS ====================

    def create_account(self, nickname, address, private_key, scheme='ed25519'):
        """Create a new account in database"""
        cursor = self.conn.cursor()
        encrypted_key = self._encrypt_private_key(private_key)
        
        try:
            cursor.execute("""
                INSERT INTO accounts (nickname, address, private_key_encrypted, scheme)
                VALUES (?, ?, ?, ?)
            """, (nickname, address, encrypted_key, scheme))
            
            account_id = cursor.lastrowid
            
            # If this is the first account, make it active
            cursor.execute("SELECT COUNT(*) FROM accounts")
            if cursor.fetchone()[0] == 1:
                self.set_active_account(account_id)
            
            self.conn.commit()
            return account_id
        except sqlite3.IntegrityError:
            return None

    def get_all_accounts(self):
        """Get all accounts (without private keys)"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, nickname, address, scheme, created_at, is_active
            FROM accounts
            ORDER BY created_at DESC
        """)
        return [dict(row) for row in cursor.fetchall()]

    def get_account_by_id(self, account_id):
        """Get account by ID"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, nickname, address, scheme, created_at, is_active
            FROM accounts WHERE id = ?
        """, (account_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_account_private_key(self, account_id):
        """Get decrypted private key for an account"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT private_key_encrypted FROM accounts WHERE id = ?
        """, (account_id,))
        row = cursor.fetchone()
        if row:
            return self._decrypt_private_key(row[0])
        return None

    def get_active_account(self):
        """Get currently active account"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, nickname, address, scheme, created_at, is_active
            FROM accounts WHERE is_active = 1
        """)
        row = cursor.fetchone()
        return dict(row) if row else None

    def set_active_account(self, account_id):
        """Set an account as active"""
        cursor = self.conn.cursor()
        # Deactivate all accounts
        cursor.execute("UPDATE accounts SET is_active = 0")
        # Activate selected account
        cursor.execute("UPDATE accounts SET is_active = 1 WHERE id = ?", (account_id,))
        self.conn.commit()
        return cursor.rowcount > 0

    def update_account_nickname(self, account_id, new_nickname):
        """Update account nickname"""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE accounts SET nickname = ? WHERE id = ?
        """, (new_nickname, account_id))
        self.conn.commit()
        return cursor.rowcount > 0

    # ==================== TRANSACTION OPERATIONS ====================

    def save_transaction(self, digest, from_address, to_address, amount, status='pending', timestamp=None):
        """Save transaction to database"""
        cursor = self.conn.cursor()
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        
        try:
            cursor.execute("""
                INSERT INTO transactions (digest, from_address, to_address, amount, status, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (digest, from_address, to_address, amount, status, timestamp))
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            # Transaction already exists
            return None

    def get_transactions_by_address(self, address, limit=20):
        """Get transactions for an address"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM transactions
            WHERE from_address = ? OR to_address = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (address, address, limit))
        return [dict(row) for row in cursor.fetchall()]

    def update_transaction_status(self, digest, status):
        """Update transaction status"""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE transactions SET status = ? WHERE digest = ?
        """, (status, digest))
        self.conn.commit()
        return cursor.rowcount > 0

    # ==================== SETTINGS OPERATIONS ====================

    def set_setting(self, key, value):
        """Set a configuration value"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO settings (key, value)
            VALUES (?, ?)
        """, (key, value))
        self.conn.commit()

    def get_setting(self, key, default=None):
        """Get a configuration value"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row[0] if row else default

    # ==================== UTILITY OPERATIONS ====================

    def close(self):
        """Close database connection"""
        self.conn.close()

    def reset_database(self):
        """Reset entire database (use with caution!)"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM accounts")
        cursor.execute("DELETE FROM transactions")
        cursor.execute("DELETE FROM settings")
        self.conn.commit()