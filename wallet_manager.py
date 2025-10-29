from pysui import SyncClient, SuiConfig
from pysui.sui.sui_crypto import SuiKeyPair, keypair_from_keystring
from pysui.sui.sui_types import SuiAddress
from database import DatabaseManager
import time
import secrets
import base64

class WalletManager:
    def __init__(self, network="testnet", max_retries=3, retry_delay=5):
        self.network = network
        
        # Initialize database
        self.db = DatabaseManager()
        
        # Initialize Sui client with retry logic
        print(f"Using custom Sui configuration for {network}...")
        self.config = SuiConfig.default_config()
        
        # Override with custom RPC URL
        if network == "testnet":
            self.config.rpc_url = "https://fullnode.testnet.sui.io:443"
        elif network == "devnet":
            self.config.rpc_url = "https://fullnode.devnet.sui.io:443"
        elif network == "mainnet":
            self.config.rpc_url = "https://fullnode.mainnet.sui.io:443"
            
        self.client = None
        self._initialize_client(max_retries, retry_delay)

    def _initialize_client(self, max_retries=3, retry_delay=5):
        """Initialize Sui client with retry logic"""
        for attempt in range(max_retries):
            try:
                print(f"🔄 Connecting to Sui {self.network} (attempt {attempt + 1}/{max_retries})...")
                self.client = SyncClient(self.config)
                
                # Test the connection
                test_result = self.client.get_rpc_api_version()
                if test_result.is_ok():
                    print(f"✅ Successfully connected to Sui {self.network}")
                    return
                else:
                    raise Exception(f"RPC API version check failed: {test_result.result_string}")
                    
            except Exception as e:
                print(f"❌ Connection attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    print(f"⏳ Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    print("💥 All connection attempts failed.")
                    try:
                        self.client = SyncClient(self.config)
                    except:
                        self.client = None

    def is_connected(self):
        """Check if client is connected to Sui network"""
        return self.client is not None

    def create_account(self, nickname="Account"):
        """Generate a REAL Sui account - FIXED VERSION"""
        try:
            print("🔄 Generating new Sui account...")
            
            # Create a new keypair using the simple constructor
            keypair = SuiKeyPair()
            
            # Get the address using the correct method
            address = keypair.address
            print(f"✅ Generated address: {address}")
            
            # Serialize the private key
            private_key = keypair.serialize()
            print(f"✅ Private key generated successfully")
            
            # Save to database
            account_id = self.db.create_account(
                nickname=nickname,
                address=str(address),
                private_key=private_key,
                scheme='ed25519'
            )
            
            if account_id:
                print(f"✅ Account saved to database with ID: {account_id}")
                
                # If this is the first account, set it as active
                accounts = self.get_all_accounts()
                if len(accounts) == 1:
                    self.switch_account(account_id)
                
                return {
                    'id': account_id,
                    'nickname': nickname,
                    'address': str(address),
                    'scheme': 'ed25519',
                    'balance': self.get_balance(str(address))
                }
            else:
                print("❌ Failed to save account to database")
                return None
                
        except Exception as e:
            print(f"❌ Error creating account: {e}")
            import traceback
            traceback.print_exc()
            return None

    def get_all_accounts(self):
        """Return all accounts from database"""
        try:
            accounts = self.db.get_all_accounts()
            # Add balance information to each account
            for account in accounts:
                account['balance'] = self.get_balance(account['address'])
            return accounts
        except Exception as e:
            print(f"Error getting accounts: {e}")
            return []

    def switch_account(self, account_id):
        """Switch to a different account"""
        success = self.db.set_active_account(account_id)
        if success:
            account = self.db.get_account_by_id(account_id)
            if account:
                account['balance'] = self.get_balance(account['address'])
            return account
        return None

    def get_active_account(self):
        """Get currently active account"""
        account = self.db.get_active_account()
        if account:
            account['balance'] = self.get_balance(account['address'])
        return account

    def get_keypair_for_account(self, account_id):
        """Get keypair for signing transactions"""
        private_key = self.db.get_account_private_key(account_id)
        if private_key:
            try:
                return keypair_from_keystring(private_key)
            except Exception as e:
                print(f"Error creating keypair: {e}")
                return None
        return None

    def get_balance(self, address):
        """Get SUI balance for an address"""
        if not self.is_connected() or not self.client:
            return 0.0
            
        try:
            result = self.client.get_balance(address=address)
            if result.is_ok():
                balance_data = result.result_data
                total_balance = int(balance_data.total_balance)
                return total_balance / 1_000_000_000
            return 0.0
        except Exception as e:
            print(f"Error fetching balance: {e}")
            return 0.0

    def send_tokens(self, from_account_id, to_address, amount):
        """Send REAL SUI tokens"""
        try:
            if not self.is_connected():
                return {'success': False, 'error': 'Not connected to network'}
            
            # Get the keypair for the sender
            keypair = self.get_keypair_for_account(from_account_id)
            if not keypair:
                return {'success': False, 'error': 'Could not get sender keypair'}
            
            # Get sender account info
            sender_account = self.db.get_account_by_id(from_account_id)
            if not sender_account:
                return {'success': False, 'error': 'Sender account not found'}
            
            sender_address = sender_account['address']
            
            print(f"🔄 Sending {amount} SUI from {sender_address} to {to_address}")
            
            # Convert amount to MIST
            amount_mist = int(amount * 1_000_000_000)
            
            # Execute transfer
            result = self.client.transfer_sui(
                signer=SuiAddress(sender_address),
                sui_object=None,
                recipient=SuiAddress(to_address),
                amount=amount_mist,
                gas_budget=2_000_000
            )
            
            if result.is_ok():
                tx_digest = result.result_data
                print(f"✅ Transfer successful! Digest: {tx_digest}")
                
                # Save transaction
                self.db.save_transaction(
                    digest=str(tx_digest),
                    from_address=sender_address,
                    to_address=to_address,
                    amount=amount,
                    status='completed'
                )
                
                return {
                    'success': True,
                    'transaction': {
                        'digest': str(tx_digest),
                        'from': sender_address,
                        'to': to_address,
                        'amount': amount,
                        'status': 'completed'
                    }
                }
            else:
                error_msg = result.result_string
                print(f"❌ Transfer failed: {error_msg}")
                return {'success': False, 'error': error_msg}
                
        except Exception as e:
            print(f"❌ Error sending tokens: {e}")
            return {'success': False, 'error': str(e)}

    def get_transaction_history(self, address):
        """Get transaction history for address"""
        try:
            return self.db.get_transactions_by_address(address)
        except Exception as e:
            print(f"Error getting transactions: {e}")
            return []

    def update_account_nickname(self, account_id, new_nickname):
        """Update account nickname"""
        return self.db.update_account_nickname(account_id, new_nickname)