from datetime import datetime
from pysui.sui.sui_txn import SyncTransaction
from pysui.sui.sui_types.scalars import SuiU64


class TransactionService:
    def __init__(self, client, wallet_manager):
        self.client = client
        self.wallet_manager = wallet_manager
        self.db = wallet_manager.db  # Access database through wallet manager

    def send_sui(self, from_account_id, to_address, amount):
        """Send SUI tokens from one account to another"""
        try:
            # Get keypair for signing
            keypair = self.wallet_manager.get_keypair_for_account(from_account_id)
            if not keypair:
                return {"success": False, "error": "Invalid account"}

            # Get account details
            from_acc = self.wallet_manager.db.get_account_by_id(from_account_id)
            if not from_acc:
                return {"success": False, "error": "Account not found"}
            
            sender = from_acc["address"]
            amount_mist = int(amount * 1_000_000_000)

            # Check balance
            balance = self.wallet_manager.get_balance(sender)
            if balance < amount:
                return {"success": False, "error": f"Insufficient balance ({balance} SUI)"}

            # Create and execute transaction
            txn = SyncTransaction(client=self.client, initial_sender=sender)
            scoin = txn.split_coin(coin=txn.gas, amounts=[SuiU64(str(amount_mist))])
            txn.transfer_objects(transfers=[scoin], recipient=to_address)
            result = txn.execute(use_gas_objects=[])

            if result.is_ok():
                data = result.result_data
                timestamp = datetime.now().isoformat()
                
                # Save transaction to database
                self.db.save_transaction(
                    digest=data.digest,
                    from_address=sender,
                    to_address=to_address,
                    amount=amount,
                    status='success',
                    timestamp=timestamp
                )
                
                return {
                    "success": True,
                    "transaction_digest": data.digest,
                    "from": sender,
                    "to": to_address,
                    "amount": amount,
                    "timestamp": timestamp,
                }
            else:
                return {"success": False, "error": f"Transaction failed: {result.result_string}"}

        except Exception as e:
            return {"success": False, "error": f"Error sending transaction: {str(e)}"}

    def get_transaction_history(self, address, limit=20):
        """Get transaction history for an address"""
        try:
            # Get from local database
            local_txs = self.db.get_transactions_by_address(address, limit)
            
            # Try to fetch from blockchain
            try:
                result = self.client.get_transactions_from_addr(address=address, limit=limit)
                
                if result.is_ok():
                    tx_data = result.result_data
                    for tx in tx_data.data:
                        digest = tx.transaction_digest
                        # Save to database if not already there
                        self.db.save_transaction(
                            digest=digest,
                            from_address=address,
                            to_address="unknown",
                            amount=0,
                            status="success",
                            timestamp=datetime.now().isoformat()
                        )
            except:
                pass  # If blockchain fetch fails, just use local data
            
            # Return local transactions
            return {
                "success": True,
                "transactions": local_txs,
                "total": len(local_txs)
            }

        except Exception as e:
            local_txs = self.db.get_transactions_by_address(address, limit)
            return {
                "success": False,
                "error": f"Error: {str(e)}",
                "transactions": local_txs,
                "total": len(local_txs)
            }