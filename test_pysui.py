"""
Test script to check if pysui is installed correctly
Run this before starting the app
"""

print("Testing PySui installation...")
print("="*60)

# Test 1: Import pysui
try:
    import pysui
    print("✅ pysui module imported")
    print(f"   Version: {pysui.__version__ if hasattr(pysui, '__version__') else 'unknown'}")
except ImportError as e:
    print(f"❌ Failed to import pysui: {e}")
    print("   Solution: pip install pysui==0.52.0")
    exit(1)

# Test 2: Import SuiKeyPair
try:
    from pysui.sui.sui_crypto import SuiKeyPair
    print("✅ SuiKeyPair imported")
except ImportError as e:
    print(f"❌ Failed to import SuiKeyPair: {e}")
    print("   Solution: pip uninstall pysui && pip install pysui==0.52.0")
    exit(1)

# Test 3: Create a keypair (using compatible method)
try:
    from pysui.sui.sui_crypto import keypair_from_keystring
    import secrets
    import base64
    
    # Generate keypair using method compatible with pysui 0.52.0
    # pysui expects: flag_byte + 32_byte_private_key, all base64 encoded
    # flag_byte: 0x00 for ED25519
    
    private_bytes = secrets.token_bytes(32)
    # Add the ED25519 scheme flag (0x00) at the start
    key_with_flag = b'\x00' + private_bytes
    # Base64 encode the whole thing
    keystring = base64.b64encode(key_with_flag).decode('utf-8')
    
    keypair = keypair_from_keystring(keystring)
    
    print("✅ Keypair created successfully")
    
    # Check what attributes/methods the keypair has
    print(f"   Keypair type: {type(keypair)}")
    print(f"   Keypair attributes: {[attr for attr in dir(keypair) if not attr.startswith('_')]}")
    
    # Try different ways to get address
    if hasattr(keypair, 'public_key'):
        print(f"   Has public_key: {keypair.public_key}")
    if hasattr(keypair, 'to_bytes'):
        print(f"   Has to_bytes method")
    
    print(f"   Keystring length: {len(keystring)}")
    
except Exception as e:
    print(f"❌ Failed to create keypair: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# Test 4: Import SyncClient
try:
    from pysui import SyncClient, SuiConfig
    print("✅ SyncClient imported")
except ImportError as e:
    print(f"❌ Failed to import SyncClient: {e}")
    exit(1)

# Test 5: Create config
try:
    config = SuiConfig.default_config()
    print("✅ SuiConfig created")
except Exception as e:
    print(f"❌ Failed to create config: {e}")
    exit(1)

# Test 6: Test database
try:
    from database import DatabaseManager
    db = DatabaseManager("test_db.db")
    print("✅ Database module working")
    
    # Clean up test database
    import os
    db.close()
    if os.path.exists("test_db.db"):
        os.remove("test_db.db")
except Exception as e:
    print(f"❌ Database error: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

print("="*60)
print("✅ ALL TESTS PASSED!")
print("   You can now run: python app.py")
print("="*60)