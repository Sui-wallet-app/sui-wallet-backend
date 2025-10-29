# Sui Wallet Web Application

A full-stack web application for managing Sui blockchain accounts and executing token transactions.

## Features

- ✅ Generate new Sui blockchain accounts
- ✅ Switch between multiple accounts
- ✅ View real-time account balances
- ✅ Send SUI tokens between accounts
- ✅ View transaction history
- ✅ Real blockchain transactions on Sui Testnet

## Tech Stack

**Backend:**
- Python 3.8+
- Flask web framework
- PySui SDK for blockchain interaction
- SQLite database with encryption

**Frontend:**
- React.js
- Axios for API calls
- Modern CSS styling

## Quick Start

### Prerequisites
- Python 3.8 or higher
- Node.js 16+ (for frontend)

### Installation

1. **Clone and setup backend:**
   ```bash
   # Create virtual environment
   python -m venv venv
   
   # Activate on Windows:
   venv\Scripts\activate
   # Activate on Mac/Linux:
   source venv/bin/activate
   
   # Install dependencies
   pip install flask flask-cors pysui cryptography