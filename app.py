from flask import Flask, jsonify, request
from flask_cors import CORS
import traceback
import sys

app = Flask(__name__)
CORS(app)

# Global wallet manager
wallet_manager = None

def initialize_wallet_manager():
    """Initialize wallet manager with detailed error reporting"""
    try:
        print("\n" + "="*60)
        print("INITIALIZING WALLET MANAGER")
        print("="*60)
        
        # Import WalletManager
        print("📦 Step 1: Importing WalletManager...")
        from wallet_manager import WalletManager
        print("✅ WalletManager imported successfully")
        
        # Create instance
        print("📦 Step 2: Creating WalletManager instance...")
        wm = WalletManager(network="testnet", max_retries=2, retry_delay=2)
        print("✅ WalletManager instance created")
        
        print("="*60)
        print("✅ WALLET MANAGER READY")
        print("="*60 + "\n")
        
        return wm
        
    except Exception as e:
        print("\n" + "="*60)
        print("💥 WALLET MANAGER INITIALIZATION FAILED")
        print("="*60)
        print(f"Error: {e}")
        print("\nFull traceback:")
        traceback.print_exc()
        print("="*60 + "\n")
        
        print("⚠️ ATTEMPTING TO CONTINUE WITHOUT NETWORK...")
        # Return None but don't crash
        return None

# Initialize on startup
print("\n🚀 Starting Sui Wallet Backend...")
wallet_manager = initialize_wallet_manager()

if wallet_manager is None:
    print("⚠️ WARNING: Wallet manager failed to initialize!")
    print("   Some features may not work.")
    print("   Check the error above and fix it before continuing.\n")

# ==================== ROUTES ====================

@app.route('/')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'running',
        'wallet_manager_initialized': wallet_manager is not None,
        'service': 'Sui Wallet Backend'
    })

@app.route('/api/health')
def api_health():
    """API health check"""
    return jsonify({
        'success': True,
        'message': 'API is running',
        'wallet_manager_initialized': wallet_manager is not None
    })

@app.route('/api/accounts', methods=['GET'])
def get_accounts():
    """Get all accounts"""
    try:
        if not wallet_manager:
            return jsonify({
                'success': False, 
                'error': 'Wallet manager not initialized. Check backend logs.'
            }), 500
        
        print("📋 Fetching all accounts...")
        accounts = wallet_manager.get_all_accounts()
        print(f"✅ Found {len(accounts)} accounts")
        
        return jsonify({
            'success': True, 
            'accounts': accounts,
            'count': len(accounts)
        })
    except Exception as e:
        print(f"❌ Error in get_accounts: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/accounts/active', methods=['GET'])
def get_active_account():
    """Get active account"""
    try:
        if not wallet_manager:
            return jsonify({
                'success': False, 
                'error': 'Wallet manager not initialized. Check backend logs.'
            }), 500
        
        print("📋 Fetching active account...")
        account = wallet_manager.get_active_account()
        
        if account:
            print(f"✅ Active account: {account['nickname']}")
        else:
            print("⚠️ No active account found")
            
        return jsonify({'success': True, 'account': account})
    except Exception as e:
        print(f"❌ Error in get_active_account: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/accounts/create', methods=['POST'])
def create_account():
    """Create new account"""
    try:
        if not wallet_manager:
            error_msg = 'Wallet manager not initialized. Check backend logs for initialization errors.'
            print(f"❌ {error_msg}")
            return jsonify({'success': False, 'error': error_msg}), 500
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No JSON data provided'}), 400
        
        nickname = data.get('nickname', 'Account')
        print(f"\n{'='*60}")
        print(f"🔄 API: Creating account '{nickname}'")
        print(f"{'='*60}")
        
        # Create account
        account = wallet_manager.create_account(nickname)
        
        if account:
            print(f"✅ API: Account created successfully")
            print(f"   ID: {account['id']}")
            print(f"   Address: {account['address'][:30]}...")
            print(f"{'='*60}\n")
            
            return jsonify({
                'success': True, 
                'account': account,
                'message': f'Account {nickname} created successfully!'
            }), 200
        else:
            print(f"❌ API: Account creation failed")
            print(f"{'='*60}\n")
            return jsonify({
                'success': False, 
                'error': 'Failed to create account. Check backend logs for details.'
            }), 500
            
    except Exception as e:
        print(f"❌ Error in create_account: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False, 
            'error': f'Internal server error: {str(e)}'
        }), 500

@app.route('/api/accounts/switch', methods=['POST'])
def switch_account():
    """Switch active account"""
    try:
        if not wallet_manager:
            return jsonify({'success': False, 'error': 'Wallet manager not initialized'}), 500
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No JSON data provided'}), 400
        
        account_id = data.get('account_id')
        if not account_id:
            return jsonify({'success': False, 'error': 'No account_id provided'}), 400
        
        print(f"🔄 Switching to account ID: {account_id}")
        
        account = wallet_manager.switch_account(account_id)
        if account:
            return jsonify({
                'success': True, 
                'account': account,
                'message': f'Switched to {account["nickname"]}'
            })
        else:
            return jsonify({
                'success': False, 
                'error': 'Failed to switch account'
            }), 404
    except Exception as e:
        print(f"❌ Error in switch_account: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/accounts/delete/<int:account_id>', methods=['DELETE'])
def delete_account(account_id):
    """Delete an account"""
    try:
        if not wallet_manager:
            return jsonify({'success': False, 'error': 'Wallet manager not initialized'}), 500
        
        print(f"🗑️ Deleting account ID: {account_id}")
        
        # Check if account exists
        account = wallet_manager.db.get_account_by_id(account_id)
        if not account:
            return jsonify({'success': False, 'error': 'Account not found'}), 404
        
        # Don't allow deleting the only account
        all_accounts = wallet_manager.get_all_accounts()
        if len(all_accounts) == 1:
            return jsonify({
                'success': False, 
                'error': 'Cannot delete the only account'
            }), 400
        
        # Check if it's the active account
        active_account = wallet_manager.get_active_account()
        was_active = active_account and active_account['id'] == account_id
        
        # Delete the account
        success = wallet_manager.db.delete_account(account_id)
        
        if success:
            # If we deleted the active account, switch to another one
            if was_active:
                remaining_accounts = wallet_manager.get_all_accounts()
                if remaining_accounts:
                    wallet_manager.switch_account(remaining_accounts[0]['id'])
            
            return jsonify({'success': True, 'message': 'Account deleted successfully'})
        else:
            return jsonify({'success': False, 'error': 'Failed to delete account'}), 500
            
    except Exception as e:
        print(f"❌ Error deleting account: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/send', methods=['POST'])
def send_tokens():
    """Send SUI tokens"""
    try:
        if not wallet_manager:
            return jsonify({'success': False, 'error': 'Wallet manager not initialized'}), 500
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No JSON data provided'}), 400
        
        from_account_id = data.get('from_account_id')
        to_address = data.get('to_address')
        amount = data.get('amount')
        
        if not all([from_account_id, to_address, amount]):
            return jsonify({
                'success': False, 
                'error': 'Missing required fields'
            }), 400
        
        result = wallet_manager.send_tokens(from_account_id, to_address, amount)
        return jsonify(result)
        
    except Exception as e:
        print(f"❌ Error in send_tokens: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/transactions/<address>', methods=['GET'])
def get_transactions(address):
    """Get transaction history"""
    try:
        if not wallet_manager:
            return jsonify({'success': False, 'error': 'Wallet manager not initialized'}), 500
        
        transactions = wallet_manager.get_transaction_history(address)
        return jsonify({
            'success': True, 
            'transactions': transactions,
            'count': len(transactions)
        })
    except Exception as e:
        print(f"❌ Error in get_transactions: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/balance/<address>', methods=['GET'])
def get_balance(address):
    """Get balance"""
    try:
        if not wallet_manager:
            return jsonify({'success': False, 'error': 'Wallet manager not initialized'}), 500
        
        balance = wallet_manager.get_balance(address)
        return jsonify({
            'success': True,
            'address': address,
            'balance': balance
        })
    except Exception as e:
        print(f"❌ Error in get_balance: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 SUI WALLET BACKEND STARTING")
    print("="*60)
    print("📍 Address: http://127.0.0.1:5000")
    print("📚 Endpoints:")
    print("   GET    /api/health")
    print("   GET    /api/accounts")
    print("   POST   /api/accounts/create")
    print("   POST   /api/accounts/switch")
    print("   DELETE /api/accounts/delete/<id>")
    print("   POST   /api/send")
    print("   GET    /api/transactions/<address>")
    
    if wallet_manager:
        if wallet_manager.is_connected():
            print("\n✅ Status: ONLINE (connected to Sui network)")
        else:
            print("\n⚠️ Status: OFFLINE (no network connection)")
    else:
        print("\n❌ Status: INITIALIZATION FAILED")
        print("   Fix the errors above before using the app")
    
    print("="*60 + "\n")
    
    app.run(debug=True, host='127.0.0.1', port=5000)