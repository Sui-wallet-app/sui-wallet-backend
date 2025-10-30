from flask import Flask, jsonify, request
from flask_cors import CORS
import traceback
import sys
import requests
import time
from collections import defaultdict
import threading

app = Flask(__name__)
CORS(app)

# Global wallet manager
wallet_manager = None

# Rate limiting storage with better management
faucet_requests = defaultdict(dict)
faucet_lock = threading.Lock()

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
        return None

def is_rate_limited(address):
    """Check if address is rate limited"""
    with faucet_lock:
        now = time.time()
        if address not in faucet_requests:
            return False
            
        last_request = faucet_requests[address].get('last_request', 0)
        consecutive_failures = faucet_requests[address].get('consecutive_failures', 0)
        
        # Base cooldown based on failures
        if consecutive_failures == 0:
            cooldown = 120  # 2 minutes after no failures
        elif consecutive_failures == 1:
            cooldown = 300  # 5 minutes after 1 failure
        else:
            cooldown = 600  # 10 minutes after multiple failures
            
        return (now - last_request) < cooldown

def update_rate_limit(address, success=False, faucet_retry_after=None):
    """Update rate limit for address"""
    with faucet_lock:
        now = time.time()
        if address not in faucet_requests:
            faucet_requests[address] = {
                'last_request': now,
                'last_success': 0,
                'consecutive_failures': 0,
                'total_requests': 0,
                'last_faucet_limit': 0
            }
        
        faucet_requests[address]['last_request'] = now
        faucet_requests[address]['total_requests'] += 1
        
        if success:
            faucet_requests[address]['last_success'] = now
            faucet_requests[address]['consecutive_failures'] = 0
            faucet_requests[address]['last_faucet_limit'] = 0
        else:
            faucet_requests[address]['consecutive_failures'] += 1
            if faucet_retry_after:
                faucet_requests[address]['last_faucet_limit'] = now + faucet_retry_after

def get_remaining_time(address):
    """Get remaining time until next allowed request"""
    with faucet_lock:
        if address not in faucet_requests:
            return 0
            
        now = time.time()
        data = faucet_requests[address]
        consecutive_failures = data.get('consecutive_failures', 0)
        last_faucet_limit = data.get('last_faucet_limit', 0)
        
        # If we have a faucet limit time, use that
        if last_faucet_limit > now:
            return int(last_faucet_limit - now)
        
        # Otherwise use our progressive cooldown
        if consecutive_failures == 0:
            cooldown = 120  # 2 minutes
        elif consecutive_failures == 1:
            cooldown = 300  # 5 minutes
        else:
            cooldown = 600  # 10 minutes
            
        last_request = data.get('last_request', 0)
        time_passed = now - last_request
        remaining = max(0, cooldown - time_passed)
        return int(remaining)

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
        
        account = wallet_manager.db.get_account_by_id(account_id)
        if not account:
            return jsonify({'success': False, 'error': 'Account not found'}), 404
        
        all_accounts = wallet_manager.get_all_accounts()
        if len(all_accounts) == 1:
            return jsonify({
                'success': False, 
                'error': 'Cannot delete the only account'
            }), 400
        
        active_account = wallet_manager.get_active_account()
        was_active = active_account and active_account['id'] == account_id
        
        success = wallet_manager.db.delete_account(account_id)
        
        if success:
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

@app.route('/api/faucet/request', methods=['POST', 'OPTIONS'])
def request_faucet():
    """Request testnet SUI from faucet"""
    # Handle OPTIONS preflight request - don't apply rate limiting to this
    if request.method == 'OPTIONS':
        return jsonify({'success': True, 'message': 'Preflight check'})
    
    try:
        if not wallet_manager:
            return jsonify({'success': False, 'error': 'Wallet manager not initialized'}), 500
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No JSON data provided'}), 400
        
        address = data.get('address')
        if not address:
            return jsonify({'success': False, 'error': 'No address provided'}), 400
        
        print(f"💰 Requesting faucet for address: {address[:20]}...")
        
        # Check our rate limit first
        if is_rate_limited(address):
            remaining_time = get_remaining_time(address)
            print(f"⏳ Our rate limit hit for {address[:20]}... (wait {remaining_time}s)")
            return jsonify({
                'success': False,
                'error': f'Please wait {remaining_time} seconds before trying again. The faucet has strict rate limits.',
                'error_code': 'RATE_LIMIT',
                'retry_after': remaining_time
            }), 429
        
        # Sui testnet faucet endpoint
        faucet_url = "https://faucet.testnet.sui.io/gas"
        
        try:
            print(f"🌐 Calling Sui faucet API...")
            response = requests.post(
                faucet_url,
                json={"FixedAmountRequest": {"recipient": address}},
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            print(f"📡 Faucet response status: {response.status_code}")
            
            if response.status_code == 200:
                print(f"✅ Faucet request successful! (200)")
                # Update rate limit on success
                update_rate_limit(address, success=True)
                
                # Wait a bit for the transaction to process
                time.sleep(5)
                
                # Get updated balance
                try:
                    balance = wallet_manager.get_balance(address)
                    print(f"💰 New balance: {balance} SUI")
                except Exception as balance_error:
                    print(f"⚠️ Could not fetch new balance: {balance_error}")
                    balance = 0
                
                return jsonify({
                    'success': True,
                    'message': 'Testnet SUI received! Your balance has been updated.',
                    'balance': balance
                })
                
            elif response.status_code == 201:
                print(f"✅ Faucet request successful! (201)")
                # Update rate limit on success
                update_rate_limit(address, success=True)
                
                # Wait a bit for the transaction to process
                time.sleep(5)
                
                # Get updated balance
                try:
                    balance = wallet_manager.get_balance(address)
                    print(f"💰 New balance: {balance} SUI")
                except Exception as balance_error:
                    print(f"⚠️ Could not fetch new balance: {balance_error}")
                    balance = 0
                
                return jsonify({
                    'success': True,
                    'message': 'Testnet SUI received! Your balance has been updated.',
                    'balance': balance
                })
                
            elif response.status_code == 429:
                print(f"⏳ Faucet service rate limit (429)")
                
                # Parse Retry-After header or use sensible defaults
                retry_after_header = response.headers.get('Retry-After')
                if retry_after_header:
                    try:
                        retry_after = int(retry_after_header)
                        print(f"📋 Using Retry-After header: {retry_after} seconds")
                    except:
                        retry_after = 300  # Default 5 minutes
                else:
                    # No Retry-After header, use progressive backoff
                    current_failures = faucet_requests.get(address, {}).get('consecutive_failures', 0)
                    if current_failures == 0:
                        retry_after = 300  # 5 minutes for first failure
                    elif current_failures == 1:
                        retry_after = 600  # 10 minutes for second failure
                    else:
                        retry_after = 900  # 15 minutes for subsequent failures
                    print(f"📋 Using progressive backoff: {retry_after} seconds")
                
                # Update our rate limit with failure and proper retry time
                update_rate_limit(address, success=False, faucet_retry_after=retry_after)
                    
                return jsonify({
                    'success': False,
                    'error': f'The Sui testnet faucet is rate limiting requests. Please wait {retry_after} seconds before trying again.',
                    'error_code': 'FAUCET_RATE_LIMIT',
                    'retry_after': retry_after
                }), 429
                
            elif response.status_code == 500:
                print(f"💥 Faucet service error (500)")
                # Update our rate limit with failure
                update_rate_limit(address, success=False, faucet_retry_after=300)
                return jsonify({
                    'success': False,
                    'error': 'The faucet service is temporarily unavailable. Please try again in 5 minutes.',
                    'error_code': 'SERVICE_UNAVAILABLE',
                    'retry_after': 300
                }), 500
                
            else:
                error_msg = f"Faucet returned status {response.status_code}"
                print(f"❌ {error_msg}")
                # Update our rate limit with failure
                update_rate_limit(address, success=False, faucet_retry_after=300)
                
                try:
                    error_detail = response.json()
                    print(f"   Response: {error_detail}")
                    error_message = error_detail.get('error', f'Faucet returned status {response.status_code}')
                except:
                    error_message = f'Faucet request failed with status {response.status_code}'
                
                return jsonify({
                    'success': False,
                    'error': error_message,
                    'error_code': 'FAUCET_ERROR',
                    'retry_after': 300
                }), response.status_code
                
        except requests.exceptions.Timeout:
            print(f"⏰ Faucet request timed out")
            update_rate_limit(address, success=False, faucet_retry_after=120)
            return jsonify({
                'success': False,
                'error': 'Faucet request timed out. The service may be busy. Please try again in 2 minutes.',
                'error_code': 'TIMEOUT',
                'retry_after': 120
            }), 500
            
        except requests.exceptions.ConnectionError:
            print(f"🔌 Connection error to faucet")
            update_rate_limit(address, success=False, faucet_retry_after=120)
            return jsonify({
                'success': False,
                'error': 'Could not connect to the faucet. Please check your internet connection and try again in 2 minutes.',
                'error_code': 'CONNECTION_ERROR',
                'retry_after': 120
            }), 500
            
        except Exception as e:
            print(f"❌ Faucet request failed: {e}")
            update_rate_limit(address, success=False, faucet_retry_after=300)
            return jsonify({
                'success': False,
                'error': f'Faucet request failed: {str(e)}',
                'error_code': 'UNKNOWN_ERROR',
                'retry_after': 300
            }), 500
            
    except Exception as e:
        print(f"❌ Error in request_faucet: {e}")
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

# Clean up old rate limit entries periodically
def cleanup_old_entries():
    """Clean up rate limit entries older than 24 hours"""
    with faucet_lock:
        now = time.time()
        expired_addresses = []
        for address, data in faucet_requests.items():
            if now - data.get('last_request', 0) > 86400:  # 24 hours
                expired_addresses.append(address)
        
        for address in expired_addresses:
            del faucet_requests[address]
        
        if expired_addresses:
            print(f"🧹 Cleaned up {len(expired_addresses)} old rate limit entries")

# Schedule cleanup (runs on every 10th request for simplicity)
cleanup_counter = 0

@app.before_request
def before_request():
    global cleanup_counter
    cleanup_counter += 1
    if cleanup_counter >= 10:
        cleanup_old_entries()
        cleanup_counter = 0

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
    print("   POST   /api/faucet/request  ⭐ FIXED RATE LIMITING!")
    print("   POST   /api/send")
    print("   GET    /api/transactions/<address>")
    print("   GET    /api/balance/<address>")
    
    if wallet_manager:
        if wallet_manager.is_connected():
            print("\n✅ Status: ONLINE (connected to Sui network)")
        else:
            print("\n⚠️ Status: OFFLINE (no network connection)")
    else:
        print("\n❌ Status: INITIALIZATION FAILED")
        print("   Fix the errors above before using the app")
    
    print("="*60)
    print("🔄 Rate limiting improvements:")
    print("   • 2 minutes cooldown after success")
    print("   • 5-15 minutes cooldown after faucet rate limits")
    print("   • Proper Retry-After header parsing")
    print("   • Progressive backoff for repeated failures")
    print("🛡️  OPTIONS requests exempt from rate limiting")
    print("🧹 Automatic cleanup of old entries (24 hours)")
    print("="*60)
    print("💡 IMPORTANT: Sui testnet faucet has strict rate limits!")
    print("   If you get rate limited, wait 5-15 minutes before retrying")
    print("="*60 + "\n")
    
    app.run(debug=True, host='127.0.0.1', port=5000)