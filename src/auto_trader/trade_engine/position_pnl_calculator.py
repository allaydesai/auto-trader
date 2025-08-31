"""P&L calculation and position analysis utilities."""

from typing import Dict, List, Any
from decimal import Decimal

from loguru import logger

from auto_trader.trade_engine.position_entry import PositionEntry


class PositionPnLCalculator:
    """Utility class for calculating P&L and position statistics."""
    
    @staticmethod
    def calculate_portfolio_unrealized_pnl(
        positions: List[PositionEntry], 
        current_prices: Dict[str, Decimal]
    ) -> Decimal:
        """Calculate total unrealized P&L for a portfolio of positions.
        
        Args:
            positions: List of open positions
            current_prices: Dictionary of symbol -> current price
            
        Returns:
            Total unrealized P&L
        """
        total_pnl = Decimal("0")
        
        for position in positions:
            if position.is_closed:
                continue
                
            current_price = current_prices.get(position.symbol)
            if current_price is None:
                logger.warning(f"No current price for {position.symbol}, skipping P&L calculation")
                continue
                
            position_pnl = position.calculate_unrealized_pnl(current_price)
            total_pnl += position_pnl
            
        return total_pnl
    
    @staticmethod
    def calculate_portfolio_realized_pnl(positions: List[PositionEntry]) -> Decimal:
        """Calculate total realized P&L for a portfolio of positions.
        
        Args:
            positions: List of positions
            
        Returns:
            Total realized P&L
        """
        total_pnl = Decimal("0")
        
        for position in positions:
            position_pnl = position.calculate_realized_pnl()
            total_pnl += position_pnl
            
        return total_pnl
    
    @staticmethod
    def get_position_summary_by_symbol(positions: List[PositionEntry]) -> Dict[str, Any]:
        """Generate position summary grouped by symbol.
        
        Args:
            positions: List of positions to analyze
            
        Returns:
            Dictionary with summary statistics by symbol
        """
        symbol_summary = {}
        
        for position in positions:
            symbol = position.symbol
            
            if symbol not in symbol_summary:
                symbol_summary[symbol] = {
                    "total_positions": 0,
                    "open_positions": 0,
                    "closed_positions": 0,
                    "total_quantity": 0,
                    "total_dollar_value": Decimal("0"),
                    "realized_pnl": Decimal("0"),
                    "position_ids": [],
                }
            
            stats = symbol_summary[symbol]
            stats["total_positions"] += 1
            stats["position_ids"].append(position.position_id)
            
            if position.is_closed:
                stats["closed_positions"] += 1
            else:
                stats["open_positions"] += 1
                stats["total_quantity"] += abs(position.remaining_quantity)
                
            stats["total_dollar_value"] += position.dollar_value
            stats["realized_pnl"] += position.calculate_realized_pnl()
        
        # Convert Decimal values to float for JSON serialization
        for symbol_stats in symbol_summary.values():
            symbol_stats["total_dollar_value"] = float(symbol_stats["total_dollar_value"])
            symbol_stats["realized_pnl"] = float(symbol_stats["realized_pnl"])
            
        return symbol_summary
    
    @staticmethod
    def get_portfolio_summary(positions: List[PositionEntry]) -> Dict[str, Any]:
        """Generate comprehensive portfolio summary.
        
        Args:
            positions: List of all positions
            
        Returns:
            Dictionary with portfolio-wide statistics
        """
        open_positions = [pos for pos in positions if not pos.is_closed]
        closed_positions = [pos for pos in positions if pos.is_closed]
        
        # Calculate P&L for closed positions
        total_realized_pnl = PositionPnLCalculator.calculate_portfolio_realized_pnl(positions)
        
        # Count symbols
        symbols_traded = set(pos.symbol for pos in positions)
        
        # Group by symbol
        symbol_breakdown = PositionPnLCalculator.get_position_summary_by_symbol(positions)
        
        # Calculate average position size
        total_dollar_value = sum(pos.dollar_value for pos in positions)
        avg_position_size = total_dollar_value / len(positions) if positions else Decimal("0")
        
        # Calculate win/loss statistics for closed positions
        winning_positions = [pos for pos in closed_positions if pos.calculate_realized_pnl() > 0]
        losing_positions = [pos for pos in closed_positions if pos.calculate_realized_pnl() < 0]
        
        win_rate = len(winning_positions) / len(closed_positions) if closed_positions else 0
        
        return {
            "total_positions": len(positions),
            "open_positions": len(open_positions),
            "closed_positions": len(closed_positions),
            "total_realized_pnl": float(total_realized_pnl),
            "symbols_traded": len(symbols_traded),
            "symbol_breakdown": symbol_breakdown,
            "average_position_size": float(avg_position_size),
            "win_rate": win_rate,
            "winning_positions": len(winning_positions),
            "losing_positions": len(losing_positions),
            "total_dollar_value": float(total_dollar_value),
        }
    
    @staticmethod
    def get_performance_metrics(positions: List[PositionEntry]) -> Dict[str, Any]:
        """Calculate detailed performance metrics.
        
        Args:
            positions: List of closed positions
            
        Returns:
            Dictionary with performance metrics
        """
        closed_positions = [pos for pos in positions if pos.is_closed]
        
        if not closed_positions:
            return {
                "total_trades": 0,
                "profit_factor": 0,
                "sharpe_ratio": None,
                "max_drawdown": 0,
                "average_win": 0,
                "average_loss": 0,
                "largest_win": 0,
                "largest_loss": 0,
            }
        
        # Calculate individual P&Ls
        pnls = [pos.calculate_realized_pnl() for pos in closed_positions]
        
        # Separate wins and losses
        wins = [pnl for pnl in pnls if pnl > 0]
        losses = [abs(pnl) for pnl in pnls if pnl < 0]
        
        # Basic statistics
        total_win_amount = sum(wins) if wins else Decimal("0")
        total_loss_amount = sum(losses) if losses else Decimal("0")
        
        profit_factor = float(total_win_amount / total_loss_amount) if total_loss_amount > 0 else float('inf')
        
        average_win = float(total_win_amount / len(wins)) if wins else 0
        average_loss = float(total_loss_amount / len(losses)) if losses else 0
        
        largest_win = float(max(wins)) if wins else 0
        largest_loss = float(max(losses)) if losses else 0
        
        # Calculate maximum drawdown
        cumulative_pnl = Decimal("0")
        peak_pnl = Decimal("0")
        max_drawdown = Decimal("0")
        
        for pnl in pnls:
            cumulative_pnl += pnl
            if cumulative_pnl > peak_pnl:
                peak_pnl = cumulative_pnl
            
            drawdown = peak_pnl - cumulative_pnl
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        return {
            "total_trades": len(closed_positions),
            "profit_factor": profit_factor,
            "sharpe_ratio": None,  # Would need time series data
            "max_drawdown": float(max_drawdown),
            "average_win": average_win,
            "average_loss": average_loss,
            "largest_win": largest_win,
            "largest_loss": largest_loss,
            "win_rate": len(wins) / len(closed_positions) if closed_positions else 0,
            "total_pnl": float(sum(pnls)),
        }