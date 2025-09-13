"""
Order Auditor for HyperTrader
Ensures actual orders match expected sliding window state
Detects and corrects discrepancies between app state and exchange orders
"""

from decimal import Decimal
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass
from loguru import logger


@dataclass
class OrderDiscrepancy:
    """Represents a mismatch between expected and actual orders"""
    unit: int
    expected_type: Optional[str]  # 'stop' or 'buy' or None
    actual_orders: List[str]  # List of order IDs actually present
    action_needed: str  # 'place', 'cancel', 'cancel_duplicates'
    

@dataclass
class AuditReport:
    """Result of an order audit"""
    timestamp: datetime
    expected_stops: List[int]
    expected_buys: List[int]
    actual_orders: Dict[int, List[str]]  # unit -> [order_ids]
    discrepancies: List[OrderDiscrepancy]
    duplicate_orders: Dict[int, List[str]]  # unit -> [duplicate_order_ids]
    orphan_orders: List[Tuple[str, Decimal]]  # [(order_id, price)] not matching any unit
    is_healthy: bool
    

class OrderAuditor:
    """
    Audits and reconciles orders to ensure sliding window integrity
    """
    
    def __init__(self, symbol: str, unit_size_usd: Decimal, tolerance: Decimal = Decimal("0.50")):
        """
        Initialize the order auditor
        
        Args:
            symbol: Trading symbol
            unit_size_usd: Unit size in USD for price matching
            tolerance: Price tolerance for matching orders to units (default $0.50)
        """
        self.symbol = symbol
        self.unit_size_usd = unit_size_usd
        self.tolerance = tolerance
        self.last_audit = None
        self.audit_count = 0
        self.corrections_made = 0
        self.last_correction = None
        
    def audit_orders(self, 
                    expected_stops: List[int],
                    expected_buys: List[int],
                    position_map: Dict,
                    live_orders: List[Dict]) -> AuditReport:
        """
        Perform comprehensive order audit
        
        Args:
            expected_stops: List of units that should have stop orders
            expected_buys: List of units that should have buy orders
            position_map: Map of unit -> PositionConfig
            live_orders: List of actual orders from exchange
            
        Returns:
            AuditReport with findings and recommendations
        """
        self.audit_count += 1
        logger.info(f"🔍 AUDIT #{self.audit_count} - Starting order reconciliation")
        
        # Map live orders to units based on price
        actual_orders = {}  # unit -> [order_ids]
        orphan_orders = []  # Orders that don't match any unit
        
        for order in live_orders:
            if order.get('symbol') != self.symbol:
                continue
                
            order_id = order.get('oid')
            price = Decimal(str(order.get('limitPx', 0)))
            side = order.get('side')  # 'A' for ask/sell, 'B' for bid/buy
            order_type = order.get('orderType')  # 'Stop', 'Limit', etc.
            
            # Try to match order to a unit based on price
            matched_unit = self._match_order_to_unit(price, position_map)
            
            if matched_unit is not None:
                if matched_unit not in actual_orders:
                    actual_orders[matched_unit] = []
                actual_orders[matched_unit].append(order_id)
            else:
                orphan_orders.append((order_id, price))
                
        # Find discrepancies
        discrepancies = []
        duplicate_orders = {}
        
        # Check expected stops
        for unit in expected_stops:
            if unit not in actual_orders:
                # Missing stop order
                discrepancies.append(OrderDiscrepancy(
                    unit=unit,
                    expected_type='stop',
                    actual_orders=[],
                    action_needed='place'
                ))
            elif len(actual_orders[unit]) > 1:
                # Duplicate orders at this unit
                duplicate_orders[unit] = actual_orders[unit][1:]  # Keep first, mark rest as duplicates
                discrepancies.append(OrderDiscrepancy(
                    unit=unit,
                    expected_type='stop',
                    actual_orders=actual_orders[unit],
                    action_needed='cancel_duplicates'
                ))
        
        # Check expected buys
        for unit in expected_buys:
            if unit not in actual_orders:
                # Missing buy order
                discrepancies.append(OrderDiscrepancy(
                    unit=unit,
                    expected_type='buy',
                    actual_orders=[],
                    action_needed='place'
                ))
            elif len(actual_orders[unit]) > 1:
                # Duplicate orders at this unit
                duplicate_orders[unit] = actual_orders[unit][1:]
                discrepancies.append(OrderDiscrepancy(
                    unit=unit,
                    expected_type='buy',
                    actual_orders=actual_orders[unit],
                    action_needed='cancel_duplicates'
                ))
        
        # Check for orders that shouldn't exist
        all_expected_units = set(expected_stops + expected_buys)
        for unit, order_ids in actual_orders.items():
            if unit not in all_expected_units:
                # Orders at unexpected unit - should be cancelled
                discrepancies.append(OrderDiscrepancy(
                    unit=unit,
                    expected_type=None,
                    actual_orders=order_ids,
                    action_needed='cancel'
                ))
        
        # Create audit report
        is_healthy = len(discrepancies) == 0 and len(orphan_orders) == 0
        
        report = AuditReport(
            timestamp=datetime.now(),
            expected_stops=expected_stops.copy(),
            expected_buys=expected_buys.copy(),
            actual_orders=actual_orders,
            discrepancies=discrepancies,
            duplicate_orders=duplicate_orders,
            orphan_orders=orphan_orders,
            is_healthy=is_healthy
        )
        
        self.last_audit = report
        self._log_audit_report(report)
        
        return report
    
    def _match_order_to_unit(self, order_price: Decimal, position_map: Dict) -> Optional[int]:
        """
        Match an order price to a unit level
        
        Args:
            order_price: Price of the order
            position_map: Map of unit -> PositionConfig
            
        Returns:
            Unit number if matched, None otherwise
        """
        for unit, config in position_map.items():
            expected_price = config.price
            
            # Check if order price is within tolerance of expected price
            if abs(order_price - expected_price) <= self.tolerance:
                return unit
                
        return None
    
    def _log_audit_report(self, report: AuditReport):
        """Log audit findings"""
        if report.is_healthy:
            logger.info(f"✅ AUDIT PASSED - All orders correctly placed")
            return
            
        logger.warning(f"⚠️ AUDIT FAILED - Found {len(report.discrepancies)} discrepancies")
        
        # Log missing orders
        missing = [d for d in report.discrepancies if d.action_needed == 'place']
        if missing:
            logger.error(f"❌ MISSING ORDERS at units: {[d.unit for d in missing]}")
        
        # Log duplicate orders
        if report.duplicate_orders:
            logger.error(f"❌ DUPLICATE ORDERS at units: {list(report.duplicate_orders.keys())}")
            for unit, order_ids in report.duplicate_orders.items():
                logger.error(f"   Unit {unit}: {len(order_ids)} duplicates - {order_ids}")
        
        # Log orphan orders
        if report.orphan_orders:
            logger.error(f"❌ ORPHAN ORDERS (not matching any unit): {len(report.orphan_orders)}")
            for order_id, price in report.orphan_orders[:5]:  # Show first 5
                logger.error(f"   Order {order_id} at ${price:.2f}")
        
        # Log unexpected orders
        unexpected = [d for d in report.discrepancies if d.action_needed == 'cancel']
        if unexpected:
            logger.error(f"❌ UNEXPECTED ORDERS at units: {[d.unit for d in unexpected]}")
    
    def get_corrections(self, report: AuditReport) -> Dict:
        """
        Get list of corrections needed based on audit report
        
        Args:
            report: AuditReport from audit_orders()
            
        Returns:
            Dict with 'place_orders' and 'cancel_orders' lists
        """
        corrections = {
            'place_orders': [],  # [(unit, order_type), ...]
            'cancel_orders': []   # [order_id, ...]
        }
        
        for discrepancy in report.discrepancies:
            if discrepancy.action_needed == 'place':
                corrections['place_orders'].append((
                    discrepancy.unit,
                    discrepancy.expected_type
                ))
            elif discrepancy.action_needed == 'cancel':
                corrections['cancel_orders'].extend(discrepancy.actual_orders)
            elif discrepancy.action_needed == 'cancel_duplicates':
                # Keep first order, cancel the rest
                if len(discrepancy.actual_orders) > 1:
                    corrections['cancel_orders'].extend(discrepancy.actual_orders[1:])
        
        # Add orphan orders to cancel list
        for order_id, _ in report.orphan_orders:
            corrections['cancel_orders'].append(order_id)
        
        return corrections
    
    async def auto_correct(self, report: AuditReport, order_manager) -> bool:
        """
        Automatically correct discrepancies found in audit
        
        Args:
            report: AuditReport with discrepancies
            order_manager: Object with place_order() and cancel_order() methods
            
        Returns:
            True if all corrections successful, False otherwise
        """
        if report.is_healthy:
            return True
            
        corrections = self.get_corrections(report)
        success = True
        
        logger.warning(f"🔧 AUTO-CORRECTION: {len(corrections['cancel_orders'])} cancels, {len(corrections['place_orders'])} places")
        
        # Cancel unwanted orders first
        for order_id in corrections['cancel_orders']:
            try:
                if await order_manager.cancel_order_by_id(order_id):
                    logger.info(f"✅ Cancelled order {order_id}")
                    self.corrections_made += 1
                else:
                    logger.error(f"❌ Failed to cancel order {order_id}")
                    success = False
            except Exception as e:
                logger.error(f"Error cancelling order {order_id}: {e}")
                success = False
        
        # Place missing orders
        for unit, order_type in corrections['place_orders']:
            try:
                if order_type == 'stop':
                    order_id = await order_manager.place_stop_loss_order(unit)
                else:  # buy
                    order_id = await order_manager.place_limit_buy_order(unit)
                    
                if order_id:
                    logger.info(f"✅ Placed {order_type} order at unit {unit}")
                    self.corrections_made += 1
                else:
                    logger.error(f"❌ Failed to place {order_type} at unit {unit}")
                    success = False
            except Exception as e:
                logger.error(f"Error placing {order_type} at unit {unit}: {e}")
                success = False
        
        self.last_correction = datetime.now()
        
        if success:
            logger.info(f"✅ AUTO-CORRECTION COMPLETE - {self.corrections_made} total corrections made")
        else:
            logger.error(f"⚠️ AUTO-CORRECTION PARTIAL - Some corrections failed")
            
        return success
    
    def should_audit(self, force: bool = False) -> bool:
        """
        Determine if an audit should be performed
        
        Args:
            force: Force audit regardless of timing
            
        Returns:
            True if audit should be performed
        """
        if force:
            return True
            
        # First audit
        if self.last_audit is None:
            return True
            
        # Regular interval (every 2 minutes)
        time_since_audit = datetime.now() - self.last_audit.timestamp
        if time_since_audit > timedelta(minutes=2):
            return True
            
        # After recent correction (wait 30 seconds then verify)
        if self.last_correction:
            time_since_correction = datetime.now() - self.last_correction
            if timedelta(seconds=30) < time_since_correction < timedelta(seconds=45):
                return True
                
        return False
    
    def get_summary(self) -> Dict:
        """Get audit summary statistics"""
        return {
            'audit_count': self.audit_count,
            'corrections_made': self.corrections_made,
            'last_audit': self.last_audit.timestamp if self.last_audit else None,
            'last_healthy': self.last_audit.is_healthy if self.last_audit else None,
            'last_discrepancies': len(self.last_audit.discrepancies) if self.last_audit else 0
        }