"""
Debug script to check database contents
Run this to see what's in your database
"""
import sqlite3
from pathlib import Path

def check_database():
    db_path = "sui_wallet.db"
    
    if not Path(db_path).exists():
        print("❌ Database file does not exist!")
        print("   The database will be created when you run app.py")
        return
    
    print("="*60)
    print("📊 CHECKING DATABASE CONTENTS")
    print("="*60)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check accounts
    print("\n📋 ACCOUNTS TABLE:")
    print("-"*60)
    cursor.execute("SELECT id, nickname, address, scheme, is_active, created_at FROM accounts")
    accounts = cursor.fetchall()
    
    if len(accounts) == 0:
        print("❌ No accounts found in database!")
        print("   Try creating an account through the UI")
    else:
        print(f"✅ Found {len(accounts)} account(s):\n")
        for acc in accounts:
            acc_id, nickname, address, scheme, is_active, created_at = acc
            status = "🟢 ACTIVE" if is_active else "⚪ Inactive"
            print(f"  {status}")
            print(f"  ID: {acc_id}")
            print(f"  Nickname: {nickname}")
            print(f"  Address: {address[:20]}...{address[-10:]}")
            print(f"  Scheme: {scheme}")
            print(f"  Created: {created_at}")
            print()
    
    # Check transactions
    print("\n💸 TRANSACTIONS TABLE:")
    print("-"*60)
    cursor.execute("SELECT COUNT(*) FROM transactions")
    tx_count = cursor.fetchone()[0]
    print(f"Found {tx_count} transaction(s)")
    
    if tx_count > 0:
        cursor.execute("SELECT digest, from_address, to_address, amount, status FROM transactions LIMIT 5")
        transactions = cursor.fetchall()
        print("\nLast 5 transactions:")
        for tx in transactions:
            digest, from_addr, to_addr, amount, status = tx
            print(f"  - {digest[:12]}... | {amount} SUI | Status: {status}")
    
    # Check database file size
    print("\n📦 DATABASE INFO:")
    print("-"*60)
    db_size = Path(db_path).stat().st_size
    print(f"  File size: {db_size:,} bytes ({db_size/1024:.2f} KB)")
    print(f"  Location: {Path(db_path).absolute()}")
    
    conn.close()
    print("\n" + "="*60)
    print("✅ Database check complete!")
    print("="*60)

if __name__ == "__main__":
    check_database()