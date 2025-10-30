from pysui import SyncClient, SuiConfig
from pysui.sui.sui_crypto import keypair_from_keystring
from pysui.sui.sui_types import SuiAddress
from database import DatabaseManager
import time
import secrets

class WalletManager:
    def __init__(self, network="testnet", max_retries=3, retry_delay=3):
        """Initialize wallet manager with database and optional network connection"""
        self.network = network
        
        # Initialize database first (this MUST work)
        print("📦 Initializing database...")
        try:
            self.db = DatabaseManager()
            print("✅ Database initialized successfully")
        except Exception as e:
            print(f"💥 CRITICAL: Database initialization failed: {e}")
            raise
        
        # Initialize network connection (this can fail gracefully)
        print(f"🔗 Connecting to Sui {network}...")
        
        # Create config programmatically without requiring client.yaml file
        rpc_url_map = {
            "testnet": "https://fullnode.testnet.sui.io:443",
            "devnet": "https://fullnode.devnet.sui.io:443",
            "mainnet": "https://fullnode.mainnet.sui.io:443"
        }
        
        self.rpc_url = rpc_url_map.get(network, rpc_url_map["testnet"])
        
        # Create a simple config object that SyncClient can use
        # SyncClient only needs an object with an rpc_url attribute
        class MinimalConfig:
            def __init__(self, rpc_url):
                self.rpc_url = rpc_url
                self.active_address = None
        
        self.config = MinimalConfig(self.rpc_url)
            
        self.client = None
        self._initialize_client(max_retries, retry_delay)

    def _initialize_client(self, max_retries=3, retry_delay=3):
        """Initialize Sui client with retry logic"""
        for attempt in range(max_retries):
            try:
                print(f"🔄 Connecting to Sui {self.network} (attempt {attempt + 1}/{max_retries})...")
                self.client = SyncClient(self.config)
                
                # Quick connection test
                test_result = self.client.get_rpc_api_version()
                if test_result.is_ok():
                    print(f"✅ Successfully connected to Sui {self.network}")
                    return
                else:
                    raise Exception(f"Connection test failed")
                    
            except Exception as e:
                print(f"⚠️ Connection attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    print(f"⏳ Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    print("⚠️ All connection attempts failed")
                    print("✅ Running in OFFLINE mode (account creation will still work)")
                    try:
                        self.client = SyncClient(self.config)
                    except:
                        self.client = None

    def _generate_ed25519_keypair(self):
        """Generate Ed25519 keypair using method compatible with pysui 0.52.0"""
        try:
            import base64
            import hashlib
            
            # Method 1: Try using the client if connected
            if self.client:
                try:
                    result = self.client.new_address()
                    if result.is_ok():
                        # Get address from result
                        address = str(result.result_data.address)
                        # Get private key from active address
                        active_address = self.config.active_address
                        if active_address:
                            keystring = active_address.keystring
                            return keystring, address
                except:
                    pass
            
            # Method 2: Generate manually using pysui's expected format
            # pysui 0.52.0 expects: flag_byte + 32_byte_private_key, all base64 encoded
            # flag_byte: 0x00 for ED25519, 0x01 for SECP256K1, 0x02 for SECP256R1
            
            # Generate 32 random bytes for private key
            private_bytes = secrets.token_bytes(32)
            
            # Add the ED25519 scheme flag (0x00) at the start
            key_with_flag = b'\x00' + private_bytes
            
            # Base64 encode the whole thing (33 bytes -> 44 chars base64)
            keystring = base64.b64encode(key_with_flag).decode('utf-8')
            
            # Create keypair to get the public key
            keypair = keypair_from_keystring(keystring)
            
            # Get the public key bytes - try different methods
            public_key_obj = keypair.public_key
            
            # Convert SuiPublicKey to bytes
            if hasattr(public_key_obj, 'to_bytes'):
                public_key_bytes = public_key_obj.to_bytes()
            elif hasattr(public_key_obj, 'serialize'):
                public_key_bytes = public_key_obj.serialize()
            elif hasattr(public_key_obj, 'to_b64'):
                # If it has to_b64, decode that
                public_key_bytes = base64.b64decode(public_key_obj.to_b64())
            else:
                # Last resort: try to convert to string and decode
                public_key_bytes = base64.b64decode(str(public_key_obj))
            
            # Derive Sui address from public key
            # Sui address = first 32 bytes of Blake2b hash of (flag + public_key)
            # where flag is the signature scheme flag (0x00 for Ed25519)
            
            # Prepend the scheme flag (0x00 for Ed25519)
            data_to_hash = b'\x00' + public_key_bytes
            
            # Hash with Blake2b
            hash_result = hashlib.blake2b(data_to_hash, digest_size=32).digest()
            
            # Take first 32 bytes and convert to hex with 0x prefix
            address = '0x' + hash_result[:32].hex()
            
            return keystring, address
            
        except Exception as e:
            print(f"❌ Keypair generation failed: {e}")
            import traceback
            traceback.print_exc()
            raise

    def create_account(self, nickname="Account"):
        """Generate a REAL working Sui account - Compatible with pysui 0.52.0"""
        try:
            print(f"\n{'='*60}")
            print(f"🔄 Creating account: {nickname}")
            print(f"{'='*60}")
            
            # Generate keypair
            print("🔑 Generating Ed25519 keypair...")
            keystring, address = self._generate_ed25519_keypair()
            
            print(f"✅ Keypair generated successfully")
            print(f"   Address: {address}")
            print(f"   Scheme: ed25519")
            
            # Save to database
            print(f"💾 Saving to database...")
            account_id = self.db.create_account(
                nickname=nickname,
                address=address,
                private_key=keystring,
                scheme='ed25519'
            )
            
            if account_id:
                print(f"✅ Account saved with ID: {account_id}")
                
                # Set as active if first account
                accounts = self.get_all_accounts()
                if len(accounts) == 1:
                    self.switch_account(account_id)
                    print(f"✅ Set as active account (first account)")
                
                # Get balance (will be 0 for new accounts)
                balance = self.get_balance(address)
                
                print(f"✅ Account creation complete!")
                print(f"{'='*60}\n")
                
                return {
                    'id': account_id,
                    'nickname': nickname,
                    'address': address,
                    'scheme': 'ed25519',
                    'balance': balance
                }
            else:
                print(f"❌ Failed to save account to database")
                print(f"{'='*60}\n")
                return None
                
        except Exception as e:
            print(f"❌ Error creating account: {e}")
            import traceback
            traceback.print_exc()
            print(f"{'='*60}\n")
            return None

    def get_all_accounts(self):
        """Get all accounts from database with balances"""
        try:
            accounts = self.db.get_all_accounts()
            for account in accounts:
                # Get fresh balance
                account['balance'] = self.get_balance(account['address'])
            return accounts
        except Exception as e:
            print(f"❌ Error getting accounts: {e}")
            import traceback
            traceback.print_exc()
            return []

    def switch_account(self, account_id):
        """Switch to a different account"""
        try:
            success = self.db.set_active_account(account_id)
            if success:
                account = self.db.get_account_by_id(account_id)
                if account:
                    account['balance'] = self.get_balance(account['address'])
                    print(f"✅ Switched to account: {account['nickname']}")
                return account
            return None
        except Exception as e:
            print(f"❌ Error switching account: {e}")
            return None

    def get_active_account(self):
        """Get currently active account"""
        try:
            account = self.db.get_active_account()
            if account:
                account['balance'] = self.get_balance(account['address'])
            return account
        except Exception as e:
            print(f"❌ Error getting active account: {e}")
            return None

    def get_keypair_for_account(self, account_id):
        """Get keypair for signing transactions"""
        try:
            private_key = self.db.get_account_private_key(account_id)
            if private_key:
                return keypair_from_keystring(private_key)
            return None
        except Exception as e:
            print(f"❌ Error creating keypair: {e}")
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
                # Convert MIST to SUI (1 SUI = 1,000,000,000 MIST)
                return total_balance / 1_000_000_000
            return 0.0
        except Exception as e:
            # Don't print error for every balance check
            return 0.0

    def is_connected(self):
        """Check if connected to network"""
        return self.client is not None

    def send_tokens(self, from_account_id, to_address, amount):
        """Send REAL SUI tokens"""
        try:
            if not self.is_connected():
                return {'success': False, 'error': 'Not connected to Sui network. Cannot send transactions in offline mode.'}
            
            # Get the keypair for the sender
            keypair = self.get_keypair_for_account(from_account_id)
            if not keypair:
                return {'success': False, 'error': 'Could not retrieve sender keypair'}
            
            # Get sender account info
            sender_account = self.db.get_account_by_id(from_account_id)
            if not sender_account:
                return {'success': False, 'error': 'Sender account not found'}
            
            sender_address = sender_account['address']
            
            # Check balance
            balance = self.get_balance(sender_address)
            if balance < amount:
                return {
                    'success': False, 
                    'error': f'Insufficient balance. Available: {balance} SUI, Required: {amount} SUI'
                }
            
            print(f"💸 Sending {amount} SUI from {sender_address[:20]}... to {to_address[:20]}...")
            
            # Convert amount to MIST (1 SUI = 1,000,000,000 MIST)
            amount_mist = int(float(amount) * 1_000_000_000)
            
            # Execute transfer using pysui
            from pysui.sui.sui_txn import SyncTransaction
            
            txn = SyncTransaction(client=self.client, initial_sender=SuiAddress(sender_address))
            split_coin = txn.split_coin(coin=txn.gas, amounts=[amount_mist])
            txn.transfer_objects(transfers=[split_coin], recipient=SuiAddress(to_address))
            
            result = txn.execute(use_gas_objects=[])
            
            if result.is_ok():
                tx_data = result.result_data
                tx_digest = tx_data.digest
                print(f"✅ Transfer successful! Digest: {tx_digest}")
                
                # Save transaction to database
                self.db.save_transaction(
                    digest=str(tx_digest),
                    from_address=sender_address,
                    to_address=to_address,
                    amount=amount,
                    status='success'
                )
                
                return {
                    'success': True,
                    'transaction': {
                        'digest': str(tx_digest),
                        'from': sender_address,
                        'to': to_address,
                        'amount': amount,
                        'status': 'success'
                    }
                }
            else:
                error_msg = result.result_string
                print(f"❌ Transfer failed: {error_msg}")
                return {'success': False, 'error': f'Transaction failed: {error_msg}'}
                
        except Exception as e:
            print(f"❌ Error sending tokens: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': f'Error: {str(e)}'}

    def get_transaction_history(self, address):
        """Get transaction history for address"""
        try:
            return self.db.get_transactions_by_address(address)
        except Exception as e:
            print(f"❌ Error getting transactions: {e}")
            return []

    def update_account_nickname(self, account_id, new_nickname):
        """Update account nickname"""
        try:
            return self.db.update_account_nickname(account_id, new_nickname)
        except Exception as e:
            print(f"❌ Error updating nickname: {e}")
            return False