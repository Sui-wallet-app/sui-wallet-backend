from flask import Flask, jsonify, request
from flask_cors import CORS
from wallet_manager import WalletManager
import time
import traceback

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Initialize wallet manager
wallet_manager = None

def initialize_wallet_manager():
    """Initialize wallet manager with comprehensive error handling"""
    try:
        wallet_manager = WalletManager(
            network="testnet", 
            max_retries=3, 
            retry_delay=5
        )
        
        if wallet_manager.is_connected():
            print("✅ Wallet manager initialized successfully with network connection")
        else:
            print("⚠️ Wallet manager initialized in offline mode (no network connection)")
            
        return wallet_manager
        
    except Exception as e:
        print(f"💥 Critical error initializing wallet manager: {e}")
        traceback.print_exc()
        return None

# Initialize wallet manager when app starts
wallet_manager = initialize_wallet_manager()

# ==================== HEALTH CHECK ROUTES ====================

@app.route('/')
def health_check():
    """Health check endpoint"""
    status = {
        'status': 'running',
        'network_connected': wallet_manager.is_connected() if wallet_manager else False,
        'service': 'Sui Wallet Backend'
    }
    return jsonify(status)

@app.route('/api/health')
def api_health():
    """API health check"""
    return jsonify({
        'success': True,
        'message': 'API is running',
        'network_connected': wallet_manager.is_connected() if wallet_manager else False
    })

# ==================== ACCOUNT ROUTES ====================

@app.route('/api/accounts', methods=['GET'])
def get_accounts():
    """Get all accounts"""
    try:
        if not wallet_manager:
            return jsonify({'success': False, 'error': 'Wallet manager not initialized'})
        
        accounts = wallet_manager.get_all_accounts()
        return jsonify({
            'success': True, 
            'accounts': accounts,
            'count': len(accounts)
        })
    except Exception as e:
        print(f"Error in get_accounts: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/accounts/active', methods=['GET'])
def get_active_account():
    """Get active account"""
    try:
        if not wallet_manager:
            return jsonify({'success': False, 'error': 'Wallet manager not initialized'})
        
        account = wallet_manager.get_active_account()
        return jsonify({'success': True, 'account': account})
    except Exception as e:
        print(f"Error in get_active_account: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/accounts/create', methods=['POST'])
def create_account():
    """Create new account"""
    try:
        if not wallet_manager:
            return jsonify({'success': False, 'error': 'Wallet manager not initialized'})
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No JSON data provided'})
        
        nickname = data.get('nickname', 'Account')
        print(f"🔄 Creating account with nickname: {nickname}")
        
        account = wallet_manager.create_account(nickname)
        if account:
            print(f"✅ Account created successfully: {account['address']}")
            return jsonify({
                'success': True, 
                'account': account,
                'message': f'Account {nickname} created successfully!'
            })
        else:
            print("❌ Account creation failed in wallet_manager")
            return jsonify({
                'success': False, 
                'error': 'Failed to create account. Please try again.'
            })
            
    except Exception as e:
        print(f"Error in create_account route: {e}")
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
            return jsonify({'success': False, 'error': 'Wallet manager not initialized'})
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No JSON data provided'})
        
        account_id = data.get('account_id')
        if not account_id:
            return jsonify({'success': False, 'error': 'No account_id provided'})
        
        print(f"🔄 Switching to account ID: {account_id}")
        
        account = wallet_manager.switch_account(account_id)
        if account:
            print(f"✅ Switched to account: {account['nickname']}")
            return jsonify({
                'success': True, 
                'account': account,
                'message': f'Switched to {account["nickname"]}'
            })
        else:
            return jsonify({
                'success': False, 
                'error': 'Failed to switch account. Account not found.'
            })
    except Exception as e:
        print(f"Error in switch_account: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== TRANSACTION ROUTES ====================

@app.route('/api/send', methods=['POST'])
def send_tokens():
    """Send REAL SUI tokens"""
    try:
        if not wallet_manager:
            return jsonify({'success': False, 'error': 'Wallet manager not initialized'})
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No JSON data provided'})
        
        from_account_id = data.get('from_account_id')
        to_address = data.get('to_address')
        amount = data.get('amount')
        
        if not all([from_account_id, to_address, amount]):
            return jsonify({
                'success': False, 
                'error': 'Missing required fields: from_account_id, to_address, amount'
            })
        
        # Use the REAL send_tokens method
        result = wallet_manager.send_tokens(from_account_id, to_address, amount)
        return jsonify(result)
        
    except Exception as e:
        print(f"Error in send_tokens: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/transactions/<address>', methods=['GET'])
def get_transactions(address):
    """Get transaction history for address"""
    try:
        if not wallet_manager:
            return jsonify({'success': False, 'error': 'Wallet manager not initialized'})
        
        transactions = wallet_manager.get_transaction_history(address)
        return jsonify({
            'success': True, 
            'transactions': transactions,
            'count': len(transactions)
        })
    except Exception as e:
        print(f"Error in get_transactions: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== BALANCE ROUTES ====================

@app.route('/api/balance/<address>', methods=['GET'])
def get_balance(address):
    """Get balance for specific address"""
    try:
        if not wallet_manager:
            return jsonify({'success': False, 'error': 'Wallet manager not initialized'})
        
        balance = wallet_manager.get_balance(address)
        return jsonify({
            'success': True,
            'address': address,
            'balance': balance
        })
    except Exception as e:
        print(f"Error in get_balance: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    print("============================================================")
    print("🚀 SUI WALLET BACKEND RUNNING")
    print("📍 http://127.0.0.1:5000")
    print("📚 Available endpoints:")
    print("   GET  /api/health")
    print("   GET  /api/accounts")
    print("   GET  /api/accounts/active")
    print("   POST /api/accounts/create")
    print("   POST /api/accounts/switch")
    print("   POST /api/send")
    print("   GET  /api/transactions/<address>")
    print("   GET  /api/balance/<address>")
    
    if wallet_manager and not wallet_manager.is_connected():
        print("⚠️ Running in OFFLINE MODE - Network operations disabled")
    print("============================================================")
    
    app.run(debug=True, host='127.0.0.1', port=5000)