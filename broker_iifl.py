"""IIFL Broker API Integration using IIFLapis SDK."""
import os
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from config import config

logger = logging.getLogger(__name__)

# Try to import IIFLapis

    
# Try to import IIFLapis

IIFLClient = None
IIFL_AVAILABLE = False

try:
    if os.getenv("TRADING_MODE", "paper").lower() != "paper":
        from IIFLapis import IIFLClient
        IIFL_AVAILABLE = True
    else:
        logger.info("Paper mode enabled. Skipping IIFLapis import.")

except ImportError:
    IIFLClient = None
    IIFL_AVAILABLE = False
    logger.warning(
        "IIFLapis SDK not installed. Install with: pip install IIFLapis"
    )
except Exception as e:
    IIFLClient = None
    IIFL_AVAILABLE = False
    logger.warning(f"IIFLapis configuration unavailable: {e}")


class IIFLBroker:
    """IIFL Securities Broker API using IIFLapis SDK."""
    
    def __init__(self):
        """Initialize IIFL Broker connection."""
        self.username = config.broker.username
        self.password = config.broker.password
        self.client = None
        self.is_logged_in = False
        self.last_ltp_cache = {}
        self.last_cache_update = {}
        
        logger.info('IIFL Broker initialized')
        logger.info(f'Username: {self.username}')
    
    def login(self) -> bool:
        """Authenticate with IIFL API.
        
        Returns:
            True if login successful
        """
        if not IIFL_AVAILABLE:
            logger.error('IIFLapis SDK not available. Install: pip install IIFLapis')
            return False
        
        try:
            logger.info('Connecting to IIFL...')
            
            # Initialize IIFL client
            self.client = IIFLClient()
            
            # Extract client code and other details from username if needed
            # Format: typically client_code
            client_code = self.username
            
            # Perform client login
            login_response = self.client.client_login(
                client_code=client_code,
                password=self.password,
                dob='',  # Use empty if not required, or extract from config
                email_id='',
                contact_number=''
            )
            
            if login_response and login_response.get('stat') == 'Ok':
                self.is_logged_in = True
                logger.info('✅ IIFL login successful')
                try:
                    from database import db
                    db.log_event('INFO', 'IIFLBroker', 'Login successful', login_response)
                except:
                    pass
                return True
            else:
                error_msg = login_response.get('emsg', 'Unknown error') if login_response else 'No response'
                logger.error(f'IIFL login failed: {error_msg}')
                try:
                    from database import db
                    db.log_event('ERROR', 'IIFLBroker', f'Login failed: {error_msg}', login_response)
                except:
                    pass
                return False
        
        except Exception as e:
            logger.error(f'IIFL login error: {e}', exc_info=True)
            try:
                from database import db
                db.log_event('ERROR', 'IIFLBroker', f'Login error: {e}')
            except:
                pass
            return False
    
    def logout(self) -> bool:
        """Logout from IIFL.
        
        Returns:
            True if successful
        """
        try:
            if self.client and self.is_logged_in:
                logger.info('Logging out from IIFL...')
                self.is_logged_in = False
                logger.info('✅ IIFL logout successful')
                return True
            return True
        except Exception as e:
            logger.error(f'IIFL logout error: {e}')
            return False
    
    def place_order(self, symbol: str, side: str, quantity: int, price: float,
                   order_type: str = 'LIMIT', product: str = 'MIS') -> Dict:
        """Place an order on IIFL.
        
        Args:
            symbol: Trading symbol (e.g., 'NIFTY' or script code)
            side: BUY or SELL
            quantity: Order quantity
            price: Order price
            order_type: LIMIT or MARKET
            product: MIS (intraday) or CNC (delivery)
        
        Returns:
            Order response dictionary
        """
        if not self.is_logged_in:
            logger.error('Not logged in to IIFL')
            return {}
        
        try:
            logger.info(f'Placing {side} order: {symbol} {quantity} @ {price}')
            
            # Map symbol to IIFL script code if needed
            scripcode = self._get_scripcode(symbol)
            
            # Determine exchange (NSE for most indices)
            exch = 'N'  # NSE
            exch_type = 'C'  # Cash
            
            # Map side to IIFL format
            side_map = {'BUY': '1', 'SELL': '2'}
            pricetyp_map = {'LIMIT': 'LMT', 'MARKET': 'MKT'}
            
            order_response = self.client.place_order(
                exch=exch,
                exchtype=exch_type,
                scripcode=scripcode,
                qty=quantity,
                price=price,
                pricetype=pricetyp_map.get(order_type, 'LMT'),
                transtype=side_map.get(side, '1'),
                producttype=product,
                ordertype='Regular',
                duration='DAY',
                ordersource='API'
            )
            
            if order_response and order_response.get('stat') == 'Ok':
                order_id = order_response.get('Norderid', '')
                logger.info(f'✅ Order placed successfully: {order_id}')
                
                return {
                    'order_id': order_id,
                    'status': 'PENDING',
                    'symbol': symbol,
                    'side': side,
                    'quantity': quantity,
                    'price': price,
                    'response': order_response
                }
            else:
                error_msg = order_response.get('emsg', 'Unknown error') if order_response else 'No response'
                logger.error(f'Order placement failed: {error_msg}')
                try:
                    from database import db
                    db.log_event('ERROR', 'IIFLBroker', f'Order failed: {error_msg}', order_response)
                except:
                    pass
                return {}
        
        except Exception as e:
            logger.error(f'Error placing order: {e}', exc_info=True)
            try:
                from database import db
                db.log_event('ERROR', 'IIFLBroker', f'Order error: {e}')
            except:
                pass
            return {}
    
    def cancel_order(self, order_id: str, exchange: str = 'N', exch_type: str = 'C') -> bool:
        """Cancel an order.
        
        Args:
            order_id: Order ID to cancel
            exchange: Exchange (default: N for NSE)
            exch_type: Exchange type (default: C for cash)
        
        Returns:
            True if successful
        """
        if not self.is_logged_in:
            logger.error('Not logged in to IIFL')
            return False
        
        try:
            logger.info(f'Cancelling order {order_id}')
            
            cancel_response = self.client.cancel_order(
                exch=exchange,
                exchtype=exch_type,
                orderno=order_id
            )
            
            if cancel_response and cancel_response.get('stat') == 'Ok':
                logger.info(f'✅ Order cancelled: {order_id}')
                return True
            else:
                error_msg = cancel_response.get('emsg', 'Unknown error') if cancel_response else 'No response'
                logger.error(f'Order cancellation failed: {error_msg}')
                return False
        
        except Exception as e:
            logger.error(f'Error cancelling order: {e}')
            return False
    
    def get_order_status(self, order_id: str) -> Dict:
        """Get order status.
        
        Args:
            order_id: Order ID
        
        Returns:
            Order status dictionary
        """
        if not self.is_logged_in:
            logger.error('Not logged in to IIFL')
            return {}
        
        try:
            # Get order book to find order status
            order_book = self.get_order_book()
            
            for order in order_book:
                if order.get('Norderid') == order_id or order.get('orderno') == order_id:
                    status_map = {
                        'All': 'OPEN',
                        'Pending': 'PENDING',
                        'Rejected': 'REJECTED',
                        'Cancelled': 'CANCELLED',
                        'Executed': 'FILLED',
                        'IOC': 'FILLED'
                    }
                    
                    return {
                        'order_id': order_id,
                        'status': status_map.get(order.get('Status'), 'UNKNOWN'),
                        'filled_qty': order.get('Filledshares', 0),
                        'pending_qty': order.get('Pendingshares', 0),
                        'average_price': order.get('Avgprice', 0),
                        'response': order
                    }
            
            logger.warning(f'Order {order_id} not found in order book')
            return {'order_id': order_id, 'status': 'NOT_FOUND'}
        
        except Exception as e:
            logger.error(f'Error getting order status: {e}')
            return {}
    
    def get_positions(self) -> List[Dict]:
        """Get open positions.
        
        Returns:
            List of position dictionaries
        """
        if not self.is_logged_in:
            logger.error('Not logged in to IIFL')
            return []
        
        try:
            logger.info('Fetching positions from IIFL...')
            
            positions_response = self.client.positions()
            
            if positions_response and positions_response.get('stat') == 'Ok':
                positions_list = positions_response.get('PoserPlData', [])
                logger.info(f'✅ Retrieved {len(positions_list)} positions')
                
                parsed_positions = []
                for pos in positions_list:
                    parsed_positions.append({
                        'symbol': pos.get('Pname', ''),
                        'exchange': pos.get('Exch', ''),
                        'side': 'BUY' if pos.get('NetQty', 0) > 0 else 'SELL',
                        'quantity': abs(pos.get('NetQty', 0)),
                        'avg_price': pos.get('PoserPrice', 0),
                        'current_price': pos.get('LTP', 0),
                        'profit_loss': pos.get('UnrealizedMTM', 0),
                        'response': pos
                    })
                
                return parsed_positions
            else:
                error_msg = positions_response.get('emsg', 'Unknown error') if positions_response else 'No response'
                logger.error(f'Failed to get positions: {error_msg}')
                return []
        
        except Exception as e:
            logger.error(f'Error getting positions: {e}', exc_info=True)
            return []
    
    def get_order_book(self) -> List[Dict]:
        """Get order book.
        
        Returns:
            List of orders
        """
        if not self.is_logged_in:
            logger.error('Not logged in to IIFL')
            return []
        
        try:
            logger.info('Fetching order book...')
            
            order_response = self.client.order_book()
            
            if order_response and order_response.get('stat') == 'Ok':
                orders = order_response.get('Orderbook', [])
                logger.info(f'✅ Retrieved {len(orders)} orders')
                return orders
            else:
                error_msg = order_response.get('emsg', 'Unknown error') if order_response else 'No response'
                logger.error(f'Failed to get order book: {error_msg}')
                return []
        
        except Exception as e:
            logger.error(f'Error getting order book: {e}')
            return []
    
    def get_candles(self, symbol: str, timeframe: int, days_back: int = 30) -> List[Dict]:
        """Get historical candles.
        
        Args:
            symbol: Trading symbol
            timeframe: Candle timeframe in minutes (e.g., 5, 15, 60)
            days_back: Number of days to fetch
        
        Returns:
            List of candle dictionaries
        """
        if not self.is_logged_in:
            logger.error('Not logged in to IIFL')
            return []
        
        try:
            logger.info(f'Fetching {days_back} days of {timeframe}min candles for {symbol}')
            
            scripcode = self._get_scripcode(symbol)
            
            # Convert timeframe to IIFL format (5m, 15m, 30m, 1h, etc.)
            interval = f'{timeframe}m' if timeframe < 60 else f'{timeframe // 60}h'
            
            # Date range
            todate = datetime.now()
            fromdate = todate - timedelta(days=days_back)
            
            candles_response = self.client.historical_candles(
                exch='N',
                exchtype='C',
                scripcode=scripcode,
                interval=interval,
                fromdate=fromdate.strftime('%Y-%m-%d'),
                todate=todate.strftime('%Y-%m-%d')
            )
            
            if candles_response and candles_response.get('stat') == 'Ok':
                candles_list = candles_response.get('gpricedata', [])
                logger.info(f'✅ Retrieved {len(candles_list)} candles')
                
                parsed_candles = []
                for candle in candles_list:
                    parsed_candles.append({
                        'time': candle.get('time', ''),
                        'open': float(candle.get('open', 0)),
                        'high': float(candle.get('high', 0)),
                        'low': float(candle.get('low', 0)),
                        'close': float(candle.get('close', 0)),
                        'volume': int(candle.get('volume', 0))
                    })
                
                return parsed_candles
            else:
                error_msg = candles_response.get('emsg', 'Unknown error') if candles_response else 'No response'
                logger.error(f'Failed to get candles: {error_msg}')
                return []
        
        except Exception as e:
            logger.error(f'Error getting candles: {e}', exc_info=True)
            return []
    
    def get_ltp(self, symbol: str) -> float:
        """Get last traded price.
        
        Args:
            symbol: Trading symbol
        
        Returns:
            Last traded price
        """
        if not self.is_logged_in:
            logger.error('Not logged in to IIFL')
            return 0.0
        
        try:
            scripcode = self._get_scripcode(symbol)
            
            # Use cache if updated recently (within 1 second)
            if symbol in self.last_ltp_cache:
                last_update = self.last_cache_update.get(symbol, datetime.now())
                if (datetime.now() - last_update).total_seconds() < 1:
                    return self.last_ltp_cache[symbol]
            
            # Fetch market feed
            req_list = [{'Exch': 'N', 'ExchType': 'C', 'ScripCode': scripcode}]
            
            feed_response = self.client.fetch_market_feed(
                req_list=req_list,
                count=1,
                client_id=self.username
            )
            
            if feed_response and len(feed_response) > 0:
                ltp = float(feed_response[0].get('LTP', 0))
                self.last_ltp_cache[symbol] = ltp
                self.last_cache_update[symbol] = datetime.now()
                return ltp
            
            logger.warning(f'No LTP data for {symbol}')
            return 0.0
        
        except Exception as e:
            logger.error(f'Error getting LTP for {symbol}: {e}')
            return 0.0
    
    def get_quote(self, symbol: str) -> Dict:
        """Get quote for a symbol.
        
        Args:
            symbol: Trading symbol
        
        Returns:
            Quote dictionary
        """
        if not self.is_logged_in:
            logger.error('Not logged in to IIFL')
            return {}
        
        try:
            scripcode = self._get_scripcode(symbol)
            req_list = [{'Exch': 'N', 'ExchType': 'C', 'ScripCode': scripcode}]
            
            feed_response = self.client.fetch_market_feed(
                req_list=req_list,
                count=1,
                client_id=self.username
            )
            
            if feed_response and len(feed_response) > 0:
                quote = feed_response[0]
                return {
                    'symbol': symbol,
                    'ltp': float(quote.get('LTP', 0)),
                    'open': float(quote.get('Open', 0)),
                    'high': float(quote.get('High', 0)),
                    'low': float(quote.get('Low', 0)),
                    'close': float(quote.get('Close', 0)),
                    'volume': int(quote.get('Volume', 0)),
                    'bid': float(quote.get('Bid', 0)),
                    'ask': float(quote.get('Ask', 0)),
                    'response': quote
                }
            
            return {}
        
        except Exception as e:
            logger.error(f'Error getting quote for {symbol}: {e}')
            return {}
    
    def modify_order(self, order_id: str, new_price: float, new_quantity: int = None,
                    exchange: str = 'N', exch_type: str = 'C') -> Dict:
        """Modify an existing order.
        
        Args:
            order_id: Order ID to modify
            new_price: New order price
            new_quantity: New quantity (optional)
            exchange: Exchange (default: N for NSE)
            exch_type: Exchange type (default: C for cash)
        
        Returns:
            Response dictionary
        """
        if not self.is_logged_in:
            logger.error('Not logged in to IIFL')
            return {}
        
        try:
            logger.info(f'Modifying order {order_id}: new_price={new_price}')
            
            modify_response = self.client.modify_order(
                exch=exchange,
                exchtype=exch_type,
                orderno=order_id,
                price=new_price,
                qty=new_quantity
            )
            
            if modify_response and modify_response.get('stat') == 'Ok':
                logger.info(f'✅ Order modified: {order_id}')
                return modify_response
            else:
                error_msg = modify_response.get('emsg', 'Unknown error') if modify_response else 'No response'
                logger.error(f'Order modification failed: {error_msg}')
                return {}
        
        except Exception as e:
            logger.error(f'Error modifying order: {e}')
            return {}
    
    def get_holdings(self) -> List[Dict]:
        """Get holdings/demat balance.
        
        Returns:
            List of holdings
        """
        if not self.is_logged_in:
            logger.error('Not logged in to IIFL')
            return []
        
        try:
            logger.info('Fetching holdings...')
            
            holdings_response = self.client.holdings()
            
            if holdings_response and holdings_response.get('stat') == 'Ok':
                holdings_list = holdings_response.get('HoldingsData', [])
                logger.info(f'✅ Retrieved {len(holdings_list)} holdings')
                return holdings_list
            else:
                error_msg = holdings_response.get('emsg', 'Unknown error') if holdings_response else 'No response'
                logger.error(f'Failed to get holdings: {error_msg}')
                return []
        
        except Exception as e:
            logger.error(f'Error getting holdings: {e}')
            return []
    
    def _get_scripcode(self, symbol: str) -> str:
        """Map symbol to IIFL script code.
        
        Args:
            symbol: Trading symbol
        
        Returns:
            Script code
        """
        # Symbol to script code mapping for common indices
        symbol_map = {
            'NIFTY': '99926000',
            'BANKNIFTY': '99926009',
            'FINNIFTY': '99926037',
            'MIDCPNIFTY': '99926048',
            'SENSEX': '99926087',
            'NIFTY50': '99926000',
            'NIFTY100': '99926001',
            'NIFTY200': '99926004',
        }
        
        # Return mapped code or use symbol as-is (assuming it's already a script code)
        return symbol_map.get(symbol.upper(), symbol)
    
    def get_connection_status(self) -> Dict:
        """Get broker connection status.
        
        Returns:
            Status dictionary
        """
        return {
            'connected': self.is_logged_in,
            'broker': 'IIFL',
            'username': self.username,
            'last_update': datetime.now().isoformat()
        }


# Global broker instance
broker = IIFLBroker()
