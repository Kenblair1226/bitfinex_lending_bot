"""
Bitfinex API integration module
"""

import os
import logging
import time
import json
import hmac
import hashlib
import base64
import requests
from typing import Dict, List, Any, Optional
import ccxt
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

class BitfinexAPI:
    """Handles all interactions with the Bitfinex API"""
    
    def __init__(self):
        """Initialize the Bitfinex API client"""
        self.api_key = os.getenv('BITFINEX_API_KEY')
        self.api_secret = os.getenv('BITFINEX_API_SECRET')
        
        if not self.api_key or not self.api_secret:
            logger.error("Bitfinex API credentials not found. Please set BITFINEX_API_KEY and BITFINEX_API_SECRET in .env file")
            raise ValueError("Bitfinex API credentials not found")
        
        # Ensure API secret is properly encoded
        try:
            # Make sure API secret is properly decoded if it's in hex format
            if all(c in '0123456789abcdefABCDEF' for c in self.api_secret) and len(self.api_secret) % 2 == 0:
                self.api_secret_bytes = bytes.fromhex(self.api_secret)
            else:
                self.api_secret_bytes = self.api_secret.encode('utf8')
        except Exception as e:
            logger.error(f"Error encoding API secret: {e}")
            # Default to UTF-8 encoding
            self.api_secret_bytes = self.api_secret.encode('utf8')
        
        # Initialize CCXT exchange object with proper encoding
        self.exchange = ccxt.bitfinex({
            'apiKey': self.api_key,
            'secret': self.api_secret,
            'enableRateLimit': True,
            'options': {
                'adjustForTimeDifference': True
            }
        })
        
        # Base URL for direct API calls
        self.base_url = "https://api.bitfinex.com"
        
        # Test connection
        try:
            self.exchange.load_markets()
            logger.info("Successfully connected to Bitfinex API")
        except Exception as e:
            logger.error(f"Failed to connect to Bitfinex API: {e}")
            raise
    
    def _make_auth_request(self, endpoint, params=None):
        """
        Make an authenticated request to Bitfinex API v1
        
        Args:
            endpoint: API endpoint (without base URL)
            params: Request parameters
            
        Returns:
            API response as JSON
        """
        if params is None:
            params = {}
            
        url = f"{self.base_url}{endpoint}"
        nonce = str(int(time.time() * 1000000))
        
        # For v1 endpoints
        if endpoint.startswith('/v1'):
            payload = {
                'request': endpoint,
                'nonce': nonce,
                **params
            }
            
            payload_json = json.dumps(payload)
            payload_encoded = base64.b64encode(payload_json.encode('utf8'))
            
            signature = hmac.new(
                self.api_secret_bytes,
                payload_encoded,
                hashlib.sha384
            ).hexdigest()
            
            headers = {
                'X-BFX-APIKEY': self.api_key,
                'X-BFX-PAYLOAD': payload_encoded.decode('utf8'),
                'X-BFX-SIGNATURE': signature
            }
            
            response = requests.post(url, headers=headers)
        
        # For v2 endpoints
        else:
            # Default to v2
            endpoint_path = f"/v2{endpoint}" if not endpoint.startswith('/v2') else endpoint
            nonce = str(int(time.time() * 1000000))
            
            body = {
                'nonce': nonce,
                'apiKey': self.api_key
            }
            
            if params:
                body.update(params)
                
            signature_payload = f'/api{endpoint_path}{nonce}{json.dumps(body)}'
            
            signature = hmac.new(
                self.api_secret_bytes,
                signature_payload.encode('utf8'),
                hashlib.sha384
            ).hexdigest()
            
            headers = {
                'bfx-nonce': nonce,
                'bfx-apikey': self.api_key,
                'bfx-signature': signature,
                'content-type': 'application/json'
            }
            
            response = requests.post(url, headers=headers, json=body)
        
        # Check for errors
        if response.status_code != 200:
            logger.error(f"API error: {response.status_code} - {response.text}")
            return {}
            
        try:
            return response.json()
        except:
            logger.error(f"Failed to decode API response: {response.text}")
            return {}
    
    def get_funding_wallet_balances(self) -> Dict[str, float]:
        """
        Retrieve balances from the funding wallet
        
        Returns:
            Dict mapping currency code to balance amount
        """
        try:
            # First try using CCXT's fetch_balance method
            try:
                balances = self.exchange.fetch_balance()
                funding_balances = {}
                
                # Check if we have a 'funding' wallet in the response
                if 'funding' in balances:
                    for currency, details in balances['funding'].items():
                        if isinstance(details, dict) and 'free' in details and details['free'] > 0:
                            funding_balances[currency.upper()] = details['free']
                        elif isinstance(details, (int, float)) and details > 0:
                            funding_balances[currency.upper()] = details
                
                # If we found balances, return them
                if funding_balances:
                    return funding_balances
                
                # Otherwise try parsing the raw response
                if 'info' in balances and isinstance(balances['info'], list):
                    for wallet_info in balances['info']:
                        if isinstance(wallet_info, list) and len(wallet_info) >= 3:
                            wallet_type = wallet_info[0]
                            currency = wallet_info[1]
                            amount = float(wallet_info[2])
                            
                            if wallet_type == 'funding' and amount > 0:
                                currency = currency.upper()
                                # Remove leading 'f' if present (Bitfinex prefixes)
                                if currency.startswith('F'):
                                    currency = currency[1:]
                                funding_balances[currency] = amount
                
                # If we found balances through raw parsing, return them
                if funding_balances:
                    return funding_balances
            except Exception as e:
                logger.warning(f"CCXT fetch_balance failed: {e}. Trying direct API call.")
            
            # If CCXT method failed, fall back to direct API call
            response = self._make_auth_request("/v2/auth/r/wallets")
            
            funding_balances = {}
            
            if isinstance(response, list):
                for wallet in response:
                    if isinstance(wallet, list) and len(wallet) >= 4:
                        wallet_type = wallet[0]
                        currency = wallet[1]
                        amount = float(wallet[2])
                        
                        if wallet_type == 'funding' and amount > 0:
                            currency = currency.upper()
                            funding_balances[currency] = amount
            
            return funding_balances
        except Exception as e:
            logger.error(f"Error fetching funding wallet balances: {e}")
            return {}
    
    def get_active_funding_offers(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Retrieve active funding offers
        
        Returns:
            Dict mapping currency code to list of offer details
        """
        try:
            # Make direct API request
            offers = self._make_auth_request("/v2/auth/r/funding/offers", {"limit": 100})
            
            # Process and organize offers by currency
            active_offers_by_currency = {}
            
            if isinstance(offers, list):
                # Log the structure of the first offer to debug
                if offers and len(offers) > 0:
                    logger.info(f"Sample offer structure: {offers[0]}")
                
                for offer in offers:
                    try:
                        if isinstance(offer, list) and len(offer) >= 16:  # Ensure we have enough elements
                            offer_id = str(offer[0]) if offer[0] is not None else "unknown"
                            symbol = str(offer[1]) if offer[1] is not None else ""
                            currency = symbol[1:] if symbol.startswith('f') else symbol
                            currency = currency.upper()
                            created_at = offer[2] if offer[2] is not None else 0
                            updated_at = offer[3] if offer[3] is not None else 0
                            
                            # Safely convert numeric values
                            try:
                                amount = float(offer[4]) if offer[4] is not None else 0.0
                            except (TypeError, ValueError):
                                amount = 0.0
                                
                            try:
                                original_amount = float(offer[5]) if offer[5] is not None else 0.0
                            except (TypeError, ValueError):
                                original_amount = 0.0
                            
                            try:
                                rate = float(offer[11]) * 365 * 100 if offer[11] is not None else 0.0
                            except (TypeError, ValueError):
                                rate = 0.0
                            
                            # Use index 15 for period based on the debug information
                            try:
                                period = int(offer[15]) if offer[15] is not None else 0
                                logger.debug(f"Period value from index 15: {period}")
                            except (TypeError, ValueError, IndexError):
                                period = 0
                            
                            offer_details = {
                                'id': offer_id,
                                'currency': currency,
                                'amount': amount,
                                'original_amount': original_amount,
                                'rate': rate,
                                'period': period,
                                'created_at': created_at,
                                'updated_at': updated_at,
                            }
                            
                            if currency not in active_offers_by_currency:
                                active_offers_by_currency[currency] = []
                            
                            active_offers_by_currency[currency].append(offer_details)
                    except Exception as e:
                        logger.warning(f"Error processing funding offer: {e}")
                        continue
            
            return active_offers_by_currency
        except Exception as e:
            logger.error(f"Error fetching active funding offers: {e}")
            return {}
    
    def get_funding_loans(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Retrieve active funding loans
        
        Returns:
            Dict mapping currency code to list of loan details
        """
        try:
            # Make direct API request
            loans = self._make_auth_request("/v2/auth/r/funding/loans", {"limit": 100})
            
            # Process and organize loans by currency
            active_loans_by_currency = {}
            
            if isinstance(loans, list):
                # Log the structure of the first loan to debug
                if loans and len(loans) > 0:
                    logger.info(f"Sample loan structure: {loans[0]}")
                
                for loan in loans:
                    try:
                        if isinstance(loan, list) and len(loan) >= 16:  # Ensure we have enough elements
                            loan_id = str(loan[0]) if loan[0] is not None else "unknown"
                            symbol = str(loan[1]) if loan[1] is not None else ""
                            currency = symbol[1:] if symbol.startswith('f') else symbol
                            currency = currency.upper()
                            created_at = loan[2] if loan[2] is not None else 0
                            updated_at = loan[3] if loan[3] is not None else 0
                            
                            # Safely convert numeric values
                            try:
                                amount = float(loan[4]) if loan[4] is not None else 0.0
                            except (TypeError, ValueError):
                                amount = 0.0
                                
                            try:
                                original_amount = float(loan[5]) if loan[5] is not None else 0.0
                            except (TypeError, ValueError):
                                original_amount = 0.0
                            
                            try:
                                rate = float(loan[11]) * 365 * 100 if loan[11] is not None else 0.0
                            except (TypeError, ValueError):
                                rate = 0.0
                            
                            # Use index 15 for period based on the debug information
                            try:
                                period = int(loan[15]) if loan[15] is not None else 0
                                logger.debug(f"Period value from index 15: {period}")
                            except (TypeError, ValueError, IndexError):
                                period = 0
                            
                            loan_details = {
                                'id': loan_id,
                                'currency': currency,
                                'amount': amount,
                                'original_amount': original_amount,
                                'rate': rate,
                                'period': period,
                                'created_at': created_at,
                                'updated_at': updated_at,
                            }
                            
                            if currency not in active_loans_by_currency:
                                active_loans_by_currency[currency] = []
                            
                            active_loans_by_currency[currency].append(loan_details)
                    except Exception as e:
                        logger.warning(f"Error processing funding loan: {e}")
                        continue
            
            return active_loans_by_currency
        except Exception as e:
            logger.error(f"Error fetching active funding loans: {e}")
            return {}
    
    def get_funding_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get comprehensive funding status for all currencies
        
        Returns:
            Dict mapping currency code to status details
        """
        try:
            # Get funding wallet balances
            balances = self.get_funding_wallet_balances()
            
            # Get active funding offers
            offers = self.get_active_funding_offers()
            
            # Get active funding loans
            loans = self.get_funding_loans()
            
            # Combine data into a comprehensive status
            funding_status = {}
            
            # Process all currencies found in any of the data sources
            all_currencies = set(list(balances.keys()) + list(offers.keys()) + list(loans.keys()))
            
            for currency in all_currencies:
                # Calculate total balance (wallet + offers + loans)
                wallet_balance = balances.get(currency, 0.0)
                
                currency_offers = offers.get(currency, [])
                total_offer_amount = sum(offer['amount'] for offer in currency_offers)
                
                currency_loans = loans.get(currency, [])
                total_loan_amount = sum(loan['amount'] for loan in currency_loans)
                
                # Get average rates
                avg_offer_rate = 0.0
                if currency_offers:
                    avg_offer_rate = sum(offer['rate'] for offer in currency_offers) / len(currency_offers)
                
                avg_loan_rate = 0.0
                if currency_loans:
                    avg_loan_rate = sum(loan['rate'] for loan in currency_loans) / len(currency_loans)
                
                # Determine lending status
                if total_loan_amount > 0:
                    lending_status = "active"
                elif total_offer_amount > 0:
                    lending_status = "offered"
                else:
                    lending_status = "inactive"
                
                # Compile status
                funding_status[currency] = {
                    'wallet_balance': wallet_balance,
                    'total_balance': wallet_balance + total_loan_amount,
                    'offered_amount': total_offer_amount,
                    'loaned_amount': total_loan_amount,
                    'num_offers': len(currency_offers),
                    'num_loans': len(currency_loans),
                    'avg_offer_rate': avg_offer_rate,
                    'avg_loan_rate': avg_loan_rate,
                    'lending_status': lending_status,
                    'offers': currency_offers,
                    'loans': currency_loans,
                }
            
            return funding_status
        except Exception as e:
            logger.error(f"Error compiling funding status: {e}")
            return {} 
    
    def get_market_lending_rates(self, currencies=None) -> Dict[str, Dict[str, Any]]:
        """
        Get current market lending rates for specified currencies
        
        Args:
            currencies: List of currency codes to get rates for. If None, gets rates for all currencies with active loans.
        
        Returns:
            Dict mapping currency code to rate details
        """
        try:
            # If no currencies specified, get all currencies with active loans
            if not currencies:
                funding_status = self.get_funding_status()
                currencies = [curr for curr, status in funding_status.items() 
                             if status.get('lending_status') == 'active']
            
            market_rates = {}
            
            # According to Bitfinex API docs, funding tickers use format "f" + currency (e.g., fUSD)
            # We'll use the public ticker endpoint which doesn't require authentication
            base_url = "https://api-pub.bitfinex.com/v2"
            
            for currency in currencies:
                try:
                    # Format the symbol according to Bitfinex API docs
                    symbol = f'f{currency}'
                    
                    # Use the public ticker endpoint
                    endpoint = f"/ticker/{symbol}"
                    url = f"{base_url}{endpoint}"
                    
                    logger.info(f"Fetching funding ticker for {symbol} from {url}")
                    response = requests.get(url)
                    
                    if response.status_code == 200:
                        # Parse the response
                        # Funding ticker format: [FRR, BID, BID_PERIOD, BID_SIZE, ASK, ASK_PERIOD, ASK_SIZE, DAILY_CHANGE, DAILY_CHANGE_RELATIVE, LAST_PRICE, VOLUME, HIGH, LOW]
                        data = response.json()
                        
                        if isinstance(data, list) and len(data) >= 10:
                            # Extract the relevant fields
                            frr = float(data[0]) if data[0] is not None else 0  # Flash Return Rate
                            bid = float(data[1]) if data[1] is not None else 0  # Bid rate
                            ask = float(data[4]) if data[4] is not None else 0  # Ask rate
                            last = float(data[9]) if data[9] is not None else 0  # Last price
                            high = float(data[11]) if len(data) > 11 and data[11] is not None else 0  # High
                            low = float(data[12]) if len(data) > 12 and data[12] is not None else 0  # Low
                            
                            # Convert daily rates to APR (multiply by 365 for days in year, 100 for percentage)
                            market_rates[currency] = {
                                'frr_rate': round(frr * 365 * 100, 2),  # Flash Return Rate as APR
                                'bid_rate': round(bid * 365 * 100, 2),  # Bid rate as APR
                                'ask_rate': round(ask * 365 * 100, 2),  # Ask rate as APR
                                'last_rate': round(last * 365 * 100, 2),  # Last rate as APR
                                'high_rate': round(high * 365 * 100, 2),  # High as APR
                                'low_rate': round(low * 365 * 100, 2),  # Low as APR
                                'timestamp': int(time.time() * 1000)
                            }
                            logger.info(f"Successfully fetched rates for {currency}: {market_rates[currency]}")
                        else:
                            logger.warning(f"Unexpected response format for {currency}: {data}")
                    else:
                        logger.warning(f"Failed to fetch rates for {currency}: HTTP {response.status_code} - {response.text}")
                except Exception as e:
                    logger.warning(f"Error fetching market rate for {currency}: {e}")
                    continue
            
            return market_rates
        except Exception as e:
            logger.error(f"Error fetching market lending rates: {e}")
            return {}