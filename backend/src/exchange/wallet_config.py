"""
Wallet configuration management for Hyperliquid trading.
Centralizes wallet and credential management.
"""

import os
from dataclasses import dataclass
from typing import Optional, Literal
from dotenv import load_dotenv
from loguru import logger


WalletType = Literal["main", "sub", "long", "short", "hedge"]


@dataclass
class WalletConfig:
    """Configuration for Hyperliquid wallet operations"""
    private_key: str
    main_wallet_address: str
    sub_wallet_address: Optional[str] = None

    def get_wallet_address(self, wallet_type: WalletType) -> str:
        """
        Get the appropriate wallet address based on wallet type.

        Args:
            wallet_type: Type of wallet to use

        Returns:
            The wallet address to use for trading
        """
        # Map wallet types to actual addresses
        if wallet_type in ["main", "long"]:
            # Long positions use main wallet
            return self.main_wallet_address
        elif wallet_type in ["sub", "hedge", "short"]:
            # Hedge/short positions use sub wallet
            if not self.sub_wallet_address:
                raise ValueError(f"Sub wallet address not configured for {wallet_type} wallet type")
            return self.sub_wallet_address
        else:
            raise ValueError(f"Unknown wallet type: {wallet_type}")

    def get_active_wallet_type(self, wallet_address: str) -> WalletType:
        """
        Determine wallet type from address.

        Args:
            wallet_address: The wallet address

        Returns:
            The wallet type
        """
        if wallet_address == self.main_wallet_address:
            return "main"
        elif wallet_address == self.sub_wallet_address:
            return "sub"
        else:
            raise ValueError(f"Unknown wallet address: {wallet_address}")

    @classmethod
    def from_env(cls) -> "WalletConfig":
        """
        Create WalletConfig from environment variables.

        Returns:
            WalletConfig instance with loaded credentials

        Raises:
            ValueError if required environment variables are missing
        """
        # Load environment variables if not already loaded
        load_dotenv()

        private_key = os.getenv("HYPERLIQUID_PRIVATE_KEY")
        if not private_key:
            raise ValueError("HYPERLIQUID_PRIVATE_KEY environment variable not set")

        main_wallet = os.getenv("HYPERLIQUID_MAIN_WALLET_ADDRESS")
        if not main_wallet:
            raise ValueError("HYPERLIQUID_MAIN_WALLET_ADDRESS environment variable not set")

        # Sub wallet is optional
        sub_wallet = os.getenv("HYPERLIQUID_SUB_WALLET_ADDRESS")

        logger.info(f"Loaded wallet configuration - Main: {main_wallet[:8]}...")
        if sub_wallet:
            logger.info(f"Sub wallet available: {sub_wallet[:8]}...")

        return cls(
            private_key=private_key,
            main_wallet_address=main_wallet,
            sub_wallet_address=sub_wallet
        )

    def mask_private_key(self) -> str:
        """Get masked version of private key for logging"""
        if len(self.private_key) > 10:
            return f"{self.private_key[:6]}...{self.private_key[-4:]}"
        return "***"