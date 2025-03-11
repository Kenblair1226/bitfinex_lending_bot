#!/usr/bin/env python3
"""
Bitfinex Funding Monitor - Main Entry Point
"""

import os
import sys
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Check for required environment variables
if not os.getenv('BITFINEX_API_KEY') or not os.getenv('BITFINEX_API_SECRET'):
    print("Error: BITFINEX_API_KEY and BITFINEX_API_SECRET must be set in a .env file")
    print("Please create a .env file with your Bitfinex API credentials:")
    print("BITFINEX_API_KEY=your_api_key")
    print("BITFINEX_API_SECRET=your_api_secret")
    sys.exit(1)

# Import the monitor module
from monitor import FundingMonitor

def main():
    """Main entry point"""
    print("Starting Bitfinex Funding Monitor...")
    monitor = FundingMonitor()
    
    try:
        monitor.run()
    except KeyboardInterrupt:
        print("\nMonitor stopped by user")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 