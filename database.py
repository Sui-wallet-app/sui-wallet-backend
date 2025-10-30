import sqlite3
from datetime import datetime
from pathlib import Path
import json
from cryptography.fernet import Fernet
import os


class DatabaseManager:
    """
    Database manager for Sui Wallet application.
    Handles account management, transaction tracking, and settings storage.
    """
    
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
            # Set restrictive permissions on key file
            os.chmod(key_file, 0o600)
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (from_address) REFERENCES accounts(address)
            )
        """)
        
        # Settings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes for better performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_transactions_from 
            ON transactions(from_address)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_transactions_to 
            ON transactions(to_address)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_transactions_timestamp 
            ON transactions(timestamp DESC)
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
        """
        Create a new account in database
        
        Args:
            nickname: Human-readable name for the account
            address: Sui blockchain address
            private_key: Private key (will be encrypted)
            scheme: Cryptographic scheme (default: ed25519)
            
        Returns:
            Account ID if successful, None if account already exists
        """
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
            FROM accounts
            WHERE id = ?
        """, (account_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_account_by_address(self, address):
        """Get account by address"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, nickname, address, scheme, created_at, is_active
            FROM accounts
            WHERE address = ?
        """, (address,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_account_private_key(self, account_id):
        """
        Get decrypted private key for an account
        
        Args:
            account_id: ID of the account
            
        Returns:
            Decrypted private key or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT private_key_encrypted
            FROM accounts
            WHERE id = ?
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
            FROM accounts
            WHERE is_active = 1
        """)
        row = cursor.fetchone()
        return dict(row) if row else None

    def set_active_account(self, account_id):
        """
        Set an account as active
        
        Args:
            account_id: ID of the account to activate
            
        Returns:
            True if successful, False otherwise
        """
        cursor = self.conn.cursor()
        
        # Deactivate all accounts
        cursor.execute("UPDATE accounts SET is_active = 0")
        
        # Activate selected account
        cursor.execute("UPDATE accounts SET is_active = 1 WHERE id = ?", (account_id,))
        self.conn.commit()
        
        return cursor.rowcount > 0

    def update_account_nickname(self, account_id, new_nickname):
        """
        Update account nickname
        
        Args:
            account_id: ID of the account
            new_nickname: New nickname for the account
            
        Returns:
            True if successful, False otherwise
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE accounts
            SET nickname = ?
            WHERE id = ?
        """, (new_nickname, account_id))
        self.conn.commit()
        
        return cursor.rowcount > 0

    def delete_account(self, account_id):
        """
        Delete an account by ID
        
        Args:
            account_id: ID of the account to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            cursor = self.conn.cursor()
            
            # Check if this is the active account
            cursor.execute('SELECT is_active FROM accounts WHERE id = ?', (account_id,))
            result = cursor.fetchone()
            
            if not result:
                print(f"⚠️ Account {account_id} not found")
                return False
            
            is_active = result[0]
            
            # Delete the account
            cursor.execute('DELETE FROM accounts WHERE id = ?', (account_id,))
            self.conn.commit()
            
            # If we deleted the active account, set another account as active
            if is_active:
                cursor.execute('SELECT id FROM accounts LIMIT 1')
                next_account = cursor.fetchone()
                if next_account:
                    self.set_active_account(next_account[0])
                    print(f"✅ Switched active account to ID: {next_account[0]}")
            
            print(f"✅ Account {account_id} deleted successfully")
            return True
            
        except Exception as e:
            print(f"❌ Error deleting account: {e}")
            import traceback
            traceback.print_exc()
            return False

    # ==================== TRANSACTION OPERATIONS ====================

    def save_transaction(self, digest, from_address, to_address, amount, 
                        status='pending', timestamp=None):
        """
        Save transaction to database
        
        Args:
            digest: Transaction digest/hash
            from_address: Sender address
            to_address: Recipient address
            amount: Transaction amount
            status: Transaction status (default: pending)
            timestamp: Transaction timestamp (default: now)
            
        Returns:
            Transaction ID if successful, None if already exists
        """
        cursor = self.conn.cursor()
        
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        
        try:
            cursor.execute("""
                INSERT INTO transactions 
                (digest, from_address, to_address, amount, status, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (digest, from_address, to_address, amount, status, timestamp))
            
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            # Transaction already exists
            return None

    def get_transactions_by_address(self, address, limit=20):
        """
        Get transactions for an address
        
        Args:
            address: Account address
            limit: Maximum number of transactions to return
            
        Returns:
            List of transaction dictionaries
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM transactions
            WHERE from_address = ? OR to_address = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (address, address, limit))
        
        return [dict(row) for row in cursor.fetchall()]

    def get_transaction_by_digest(self, digest):
        """Get a specific transaction by digest"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM transactions
            WHERE digest = ?
        """, (digest,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def update_transaction_status(self, digest, status):
        """
        Update transaction status
        
        Args:
            digest: Transaction digest
            status: New status
            
        Returns:
            True if successful, False otherwise
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE transactions
            SET status = ?
            WHERE digest = ?
        """, (status, digest))
        self.conn.commit()
        
        return cursor.rowcount > 0

    def get_transaction_stats(self, address):
        """
        Get transaction statistics for an address
        
        Returns:
            Dictionary with total sent, received, and transaction count
        """
        cursor = self.conn.cursor()
        
        # Total sent
        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0) as total_sent
            FROM transactions
            WHERE from_address = ? AND status = 'success'
        """, (address,))
        total_sent = cursor.fetchone()[0]
        
        # Total received
        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0) as total_received
            FROM transactions
            WHERE to_address = ? AND status = 'success'
        """, (address,))
        total_received = cursor.fetchone()[0]
        
        # Transaction count
        cursor.execute("""
            SELECT COUNT(*) as total_txs
            FROM transactions
            WHERE from_address = ? OR to_address = ?
        """, (address, address))
        total_txs = cursor.fetchone()[0]
        
        return {
            'total_sent': total_sent,
            'total_received': total_received,
            'total_transactions': total_txs,
            'net_flow': total_received - total_sent
        }

    # ==================== SETTINGS OPERATIONS ====================

    def set_setting(self, key, value):
        """
        Set a configuration value
        
        Args:
            key: Setting key
            value: Setting value (will be converted to string)
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (key, str(value)))
        self.conn.commit()

    def get_setting(self, key, default=None):
        """
        Get a configuration value
        
        Args:
            key: Setting key
            default: Default value if key not found
            
        Returns:
            Setting value or default
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row[0] if row else default

    def get_all_settings(self):
        """Get all settings as a dictionary"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT key, value FROM settings")
        return {row[0]: row[1] for row in cursor.fetchall()}

    def delete_setting(self, key):
        """Delete a setting"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM settings WHERE key = ?", (key,))
        self.conn.commit()
        return cursor.rowcount > 0

    # ==================== UTILITY OPERATIONS ====================

    def backup_database(self, backup_path=None):
        """
        Create a backup of the database
        
        Args:
            backup_path: Path for backup file (default: db_name_backup_timestamp.db)
            
        Returns:
            Path to backup file
        """
        if backup_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"{self.db_path}_backup_{timestamp}.db"
        
        # Use SQLite backup API
        backup_conn = sqlite3.connect(backup_path)
        with backup_conn:
            self.conn.backup(backup_conn)
        backup_conn.close()
        
        return backup_path

    def reset_database(self):
        """Reset entire database (use with caution!)"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM accounts")
        cursor.execute("DELETE FROM transactions")
        cursor.execute("DELETE FROM settings")
        self.conn.commit()
        print("✅ Database reset complete")

    def get_database_info(self):
        """Get database statistics"""
        cursor = self.conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM accounts")
        account_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM transactions")
        transaction_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM settings")
        setting_count = cursor.fetchone()[0]
        
        # Get database size
        db_size = Path(self.db_path).stat().st_size if Path(self.db_path).exists() else 0
        
        return {
            'accounts': account_count,
            'transactions': transaction_count,
            'settings': setting_count,
            'database_size_bytes': db_size,
            'database_size_kb': round(db_size / 1024, 2),
            'database_path': self.db_path
        }

    def close(self):
        """Close database connection"""
        self.conn.close()

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()

    def __del__(self):
        """Destructor to ensure connection is closed"""
        try:
            self.conn.close()
        except:
            pass


# Example usage
if __name__ == "__main__":
    # Initialize database
    db = DatabaseManager("test_wallet.db")
    
    # Create a test account
    account_id = db.create_account(
        nickname="My Main Wallet",
        address="0x1234567890abcdef",
        private_key="test_private_key_do_not_use_in_production"
    )
    
    if account_id:
        print(f"✅ Created account with ID: {account_id}")
        
        # Get all accounts
        accounts = db.get_all_accounts()
        print(f"\n📋 All accounts: {len(accounts)}")
        for acc in accounts:
            print(f"  - {acc['nickname']} ({acc['address'][:10]}...)")
        
        # Save a test transaction
        tx_id = db.save_transaction(
            digest="0xabcdef123456",
            from_address="0x1234567890abcdef",
            to_address="0xfedcba0987654321",
            amount=100.5,
            status="success"
        )
        print(f"\n✅ Saved transaction with ID: {tx_id}")
        
        # Get database info
        info = db.get_database_info()
        print(f"\n📊 Database info:")
        for key, value in info.items():
            print(f"  {key}: {value}")
    
    # Close connection
    db.close()
    print("\n✅ Database connection closed")