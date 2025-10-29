"""
Migration script to move from JSON file storage to SQLite database
Run this once to migrate your existing accounts
"""

import json
from pathlib import Path
from database import DatabaseManager


def migrate_accounts():
    """Migrate accounts from JSON files to database"""
    
    # Initialize database
    db = DatabaseManager()
    
    # Check for old accounts file
    accounts_file = Path("wallet_data/accounts.json")
    active_account_file = Path("wallet_data/active_account.json")
    
    if not accounts_file.exists():
        print("No old accounts found. Starting fresh!")
        return
    
    # Load old accounts
    with open(accounts_file, 'r') as f:
        old_accounts = json.load(f)
    
    # Load active account index
    active_index = 0
    if active_account_file.exists():
        with open(active_account_file, 'r') as f:
            data = json.load(f)
            active_index = data.get('active_index', 0)
    
    print(f"Found {len(old_accounts)} accounts to migrate...")
    
    # Migrate each account
    migrated = 0
    for acc in old_accounts:
        try:
            account_id = db.create_account(
                nickname=acc['nickname'],
                address=acc['address'],
                private_key=acc['private_key'],
                scheme=acc.get('scheme', 'ed25519')
            )
            
            if account_id:
                migrated += 1
                print(f"✓ Migrated: {acc['nickname']} ({acc['address'][:10]}...)")
                
                # Set active account
                if acc['id'] == active_index:
                    db.set_active_account(account_id)
                    print(f"  → Set as active account")
            else:
                print(f"✗ Failed to migrate: {acc['nickname']} (might already exist)")
        
        except Exception as e:
            print(f"✗ Error migrating {acc['nickname']}: {e}")
    
    print(f"\n✓ Migration complete! {migrated}/{len(old_accounts)} accounts migrated.")
    print("\nYou can now safely delete the 'wallet_data' folder.")
    print("Your data is now stored in 'sui_wallet.db'")
    

def verify_migration():
    """Verify the migration was successful"""
    db = DatabaseManager()
    accounts = db.get_all_accounts()
    active = db.get_active_account()
    
    print("\n" + "="*50)
    print("Database Verification")
    print("="*50)
    print(f"Total accounts: {len(accounts)}")
    print(f"Active account: {active['nickname'] if active else 'None'}")
    print("\nAccounts:")
    for acc in accounts:
        status = "🟢 ACTIVE" if acc['is_active'] else ""
        print(f"  - {acc['nickname']}: {acc['address'][:20]}... {status}")
    print("="*50)


if __name__ == "__main__":
    print("="*50)
    print("Sui Wallet - Database Migration Tool")
    print("="*50)
    print("\nThis will migrate your accounts from JSON files to SQLite database.")
    print("Your private keys will be encrypted in the new database.")
    
    response = input("\nProceed with migration? (y/n): ")
    
    if response.lower() == 'y':
        migrate_accounts()
        verify_migration()
    else:
        print("Migration cancelled.")