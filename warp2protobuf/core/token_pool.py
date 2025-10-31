#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Multi-Token Pool Manager for Warp API

Manages multiple refresh tokens with priority-based selection and automatic failover.
Supports personal tokens (high priority) and anonymous tokens (low priority).
"""
import asyncio
import base64
import json
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set
import httpx
from dotenv import load_dotenv, set_key

from ..config.settings import REFRESH_TOKEN_B64, REFRESH_URL, CLIENT_VERSION, OS_CATEGORY, OS_NAME, OS_VERSION
from .logging import logger


class TokenPriority(Enum):
    """Token priority levels"""
    ANONYMOUS = 1     # Anonymous tokens (highest priority - to save personal quota)
    SHARED = 2        # Shared tokens (medium priority)
    PERSONAL = 3      # Personal tokens (lowest priority - save for when anonymous fails)


@dataclass
class TokenInfo:
    """Information about a refresh token"""
    refresh_token: str
    priority: TokenPriority
    name: str = ""
    last_used: float = 0.0
    failure_count: int = 0
    is_active: bool = True
    last_jwt: str = ""
    last_jwt_expiry: float = 0.0
    
    def __post_init__(self):
        if not self.name:
            # Generate a short name from token hash
            token_hash = hash(self.refresh_token) % 10000
            self.name = f"{self.priority.name}_{token_hash:04d}"


class TokenPool:
    """
    Multi-token pool manager with priority-based selection.
    
    Features:
    - Priority-based token selection (Personal > Shared > Anonymous)
    - Round-robin within same priority level
    - Automatic failover on token failure
    - Health monitoring and auto-recovery
    - Thread-safe operations
    """
    
    def __init__(self):
        self._tokens: List[TokenInfo] = []
        self._lock = asyncio.Lock()
        self._current_index: Dict[TokenPriority, int] = {
            TokenPriority.PERSONAL: 0,
            TokenPriority.SHARED: 0,
            TokenPriority.ANONYMOUS: 0,
        }
        self._last_used_index: Dict[TokenPriority, int] = {
            TokenPriority.PERSONAL: 0,
            TokenPriority.SHARED: 0,
            TokenPriority.ANONYMOUS: 0,
        }
        self._failed_tokens: Set[str] = set()
        self._max_failures = 3  # Max failures before marking token as inactive
        self._initialized = False
    
    async def initialize(self):
        """Initialize token pool from environment variables"""
        async with self._lock:
            if self._initialized:
                return
            
            logger.info("🔄 Initializing token pool...")

            # Load anonymous/fallback token (highest priority - to save personal quota)
            anonymous_token = self._load_anonymous_token()
            if anonymous_token:
                self._add_token_internal(anonymous_token, TokenPriority.ANONYMOUS)

            # Load shared tokens (medium priority)
            shared_tokens = self._load_shared_tokens()
            for token in shared_tokens:
                self._add_token_internal(token, TokenPriority.SHARED)

            # Load personal tokens (lowest priority - save for when anonymous fails)
            personal_tokens = self._load_personal_tokens()
            for token in personal_tokens:
                self._add_token_internal(token, TokenPriority.PERSONAL)
            
            self._initialized = True
            self._log_pool_status()
    
    def _load_personal_tokens(self) -> List[str]:
        """Load personal refresh tokens from environment"""
        tokens = []
        
        # Single personal token
        personal_token = os.getenv("WARP_REFRESH_TOKEN")
        if personal_token and personal_token.strip() and personal_token != "your_warp_refresh_token_here":
            tokens.append(personal_token.strip())
            logger.info(f"✅ Loaded personal token from WARP_REFRESH_TOKEN")
        
        # Multiple personal tokens (comma-separated)
        personal_tokens_str = os.getenv("WARP_PERSONAL_TOKENS")
        if personal_tokens_str:
            for token in personal_tokens_str.split(','):
                token = token.strip()
                if token and token not in tokens:
                    tokens.append(token)
            if personal_tokens_str.strip():
                logger.info(f"✅ Loaded {len(personal_tokens_str.split(','))} personal tokens from WARP_PERSONAL_TOKENS")
        
        return tokens
    
    def _load_shared_tokens(self) -> List[str]:
        """Load shared refresh tokens from environment"""
        tokens = []
        
        shared_tokens_str = os.getenv("WARP_SHARED_TOKENS")
        if shared_tokens_str:
            for token in shared_tokens_str.split(','):
                token = token.strip()
                if token:
                    tokens.append(token)
            if shared_tokens_str.strip():
                logger.info(f"✅ Loaded {len(tokens)} shared tokens from WARP_SHARED_TOKENS")
        
        return tokens
    
    def _load_anonymous_token(self) -> Optional[str]:
        """Load anonymous/fallback token"""
        # Try environment variable first
        anon_token = os.getenv("WARP_ANONYMOUS_TOKEN")
        if anon_token and anon_token.strip():
            logger.info("✅ Loaded anonymous token from WARP_ANONYMOUS_TOKEN")
            return anon_token.strip()
        
        # Fall back to built-in token
        try:
            decoded = base64.b64decode(REFRESH_TOKEN_B64).decode('utf-8')
            # Extract refresh_token from "grant_type=refresh_token&refresh_token=XXX"
            if "refresh_token=" in decoded:
                token = decoded.split("refresh_token=")[1]
                logger.info("✅ Loaded built-in anonymous token")
                return token
        except Exception as e:
            logger.warning(f"⚠️ Failed to decode built-in token: {e}")
        
        return None
    
    def _add_token_internal(self, refresh_token: str, priority: TokenPriority):
        """Add a token to the pool (internal, no lock)"""
        # Check if token already exists
        for token_info in self._tokens:
            if token_info.refresh_token == refresh_token:
                logger.debug(f"Token already in pool: {token_info.name}")
                return
        
        token_info = TokenInfo(
            refresh_token=refresh_token,
            priority=priority
        )
        self._tokens.append(token_info)
        logger.debug(f"➕ Added token: {token_info.name} (priority: {priority.name})")
    
    async def add_token(self, refresh_token: str, priority: TokenPriority = TokenPriority.SHARED):
        """Add a new token to the pool"""
        async with self._lock:
            self._add_token_internal(refresh_token, priority)
            self._log_pool_status()
    
    async def get_next_token(self) -> Optional[TokenInfo]:
        """
        Get the next available token based on priority and round-robin.
        
        Returns:
            TokenInfo if available, None if no tokens available
        """
        if not self._initialized:
            await self.initialize()
        
        async with self._lock:
            # Try each priority level in order (ANONYMOUS first to save personal quota)
            for priority in [TokenPriority.ANONYMOUS, TokenPriority.SHARED, TokenPriority.PERSONAL]:
                token = self._get_token_by_priority(priority)
                if token:
                    token.last_used = time.time()
                    logger.debug(f"🎯 Selected token: {token.name} (priority: {priority.name})")
                    return token

            logger.error("❌ No available tokens in pool!")
            return None
    
    def _get_token_by_priority(self, priority: TokenPriority) -> Optional[TokenInfo]:
        """Get next token of specific priority using round-robin"""
        # Get all active tokens of this priority
        priority_tokens = [
            t for t in self._tokens 
            if t.priority == priority and t.is_active and t.refresh_token not in self._failed_tokens
        ]
        
        if not priority_tokens:
            return None
        
        # Round-robin selection
        current_idx = self._current_index[priority]
        token = priority_tokens[current_idx % len(priority_tokens)]
        
        # Update index for next call
        self._current_index[priority] = (current_idx + 1) % len(priority_tokens)
        
        return token
    
    def get_last_used_token(self) -> Optional[TokenInfo]:
        """
        Get the most recently used token.

        Returns:
            TokenInfo if available, None if no tokens have been used
        """
        if not self._tokens:
            return None

        # Find the token with the most recent last_used timestamp
        most_recent = None
        for token in self._tokens:
            if token.last_used > 0:
                if most_recent is None or token.last_used > most_recent.last_used:
                    most_recent = token

        return most_recent

    async def get_next_token_excluding(self, exclude_token: Optional[str] = None) -> Optional[TokenInfo]:
        """
        Get the next available token, excluding a specific token.
        Useful when current token fails and we need to try a different one.

        Args:
            exclude_token: refresh_token string to exclude from selection

        Returns:
            TokenInfo if available, None if no other tokens available
        """
        if not self._initialized:
            await self.initialize()

        async with self._lock:
            # Try each priority level in order (ANONYMOUS first to save personal quota)
            for priority in [TokenPriority.ANONYMOUS, TokenPriority.SHARED, TokenPriority.PERSONAL]:
                # Get all active tokens of this priority, excluding the specified token
                priority_tokens = [
                    t for t in self._tokens
                    if t.priority == priority
                    and t.is_active
                    and t.refresh_token not in self._failed_tokens
                    and (exclude_token is None or t.refresh_token != exclude_token)
                ]

                if priority_tokens:
                    # Use round-robin within same priority
                    if priority not in self._last_used_index:
                        self._last_used_index[priority] = 0

                    idx = self._last_used_index[priority] % len(priority_tokens)
                    token = priority_tokens[idx]
                    self._last_used_index[priority] = (idx + 1) % len(priority_tokens)

                    token.last_used = time.time()
                    logger.debug(f"🎯 Selected token (excluding {exclude_token[:20] if exclude_token else 'none'}...): {token.name} (priority: {priority.name})")
                    return token

            logger.error("❌ No other available tokens in pool!")
            return None

    async def mark_token_failed(self, token_info: TokenInfo):
        """Mark a token as failed and potentially deactivate it"""
        async with self._lock:
            token_info.failure_count += 1

            if token_info.failure_count >= self._max_failures:
                token_info.is_active = False
                self._failed_tokens.add(token_info.refresh_token)
                logger.warning(f"⚠️ Token deactivated after {self._max_failures} failures: {token_info.name}")
            else:
                logger.warning(f"⚠️ Token failure {token_info.failure_count}/{self._max_failures}: {token_info.name}")
    
    async def mark_token_success(self, token_info: TokenInfo, jwt: str = "", jwt_expiry: float = 0.0):
        """Mark a token as successful and reset failure count"""
        async with self._lock:
            token_info.failure_count = 0
            if token_info.refresh_token in self._failed_tokens:
                self._failed_tokens.remove(token_info.refresh_token)
            
            if jwt:
                token_info.last_jwt = jwt
                token_info.last_jwt_expiry = jwt_expiry
    
    async def get_pool_stats(self) -> Dict:
        """Get statistics about the token pool"""
        async with self._lock:
            stats = {
                "total_tokens": len(self._tokens),
                "active_tokens": sum(1 for t in self._tokens if t.is_active),
                "failed_tokens": len(self._failed_tokens),
                "by_priority": {}
            }

            for priority in TokenPriority:
                priority_tokens = [t for t in self._tokens if t.priority == priority]
                active_count = sum(1 for t in priority_tokens if t.is_active)
                stats["by_priority"][priority.name] = {
                    "total": len(priority_tokens),
                    "active": active_count,
                    "inactive": len(priority_tokens) - active_count
                }

            # Add convenience keys for direct access
            stats["personal_tokens"] = stats["by_priority"].get("PERSONAL", {}).get("active", 0)
            stats["shared_tokens"] = stats["by_priority"].get("SHARED", {}).get("active", 0)
            stats["anonymous_tokens"] = stats["by_priority"].get("ANONYMOUS", {}).get("active", 0)

            return stats
    
    def _log_pool_status(self):
        """Log current pool status"""
        total = len(self._tokens)
        active = sum(1 for t in self._tokens if t.is_active)

        by_priority = {}
        # Show in priority order (ANONYMOUS first)
        for priority in [TokenPriority.ANONYMOUS, TokenPriority.SHARED, TokenPriority.PERSONAL]:
            count = sum(1 for t in self._tokens if t.priority == priority and t.is_active)
            if count > 0:
                by_priority[priority.name] = count

        priority_str = ", ".join(f"{k}: {v}" for k, v in by_priority.items())
        logger.info(f"📊 Token Pool: {active}/{total} active tokens (优先级: {priority_str})")

    async def health_check(self) -> Dict:
        """
        Perform health check on all tokens.

        Returns:
            Dict with health check results
        """
        async with self._lock:
            results = {
                "timestamp": time.time(),
                "total_tokens": len(self._tokens),
                "healthy_tokens": 0,
                "unhealthy_tokens": 0,
                "tokens": []
            }

            for token_info in self._tokens:
                is_healthy = token_info.is_active and token_info.refresh_token not in self._failed_tokens

                token_status = {
                    "name": token_info.name,
                    "priority": token_info.priority.name,
                    "is_active": token_info.is_active,
                    "is_healthy": is_healthy,
                    "failure_count": token_info.failure_count,
                    "last_used": token_info.last_used,
                    "has_cached_jwt": bool(token_info.last_jwt),
                }

                if token_info.last_jwt_expiry > 0:
                    time_until_expiry = token_info.last_jwt_expiry - time.time()
                    token_status["jwt_expires_in"] = max(0, time_until_expiry)

                results["tokens"].append(token_status)

                if is_healthy:
                    results["healthy_tokens"] += 1
                else:
                    results["unhealthy_tokens"] += 1

            return results

    async def recover_failed_tokens(self):
        """
        Attempt to recover failed tokens by resetting their failure count.
        This can be called periodically to give failed tokens another chance.
        """
        async with self._lock:
            recovered = 0
            for token_info in self._tokens:
                if not token_info.is_active and token_info.failure_count >= self._max_failures:
                    # Reset failure count and reactivate
                    token_info.failure_count = 0
                    token_info.is_active = True
                    if token_info.refresh_token in self._failed_tokens:
                        self._failed_tokens.remove(token_info.refresh_token)
                    recovered += 1
                    logger.info(f"🔄 Recovered token: {token_info.name}")

            if recovered > 0:
                logger.info(f"✅ Recovered {recovered} failed tokens")
                self._log_pool_status()

            return recovered


# Global token pool instance
_token_pool: Optional[TokenPool] = None


async def get_token_pool() -> TokenPool:
    """Get or create the global token pool instance"""
    global _token_pool
    if _token_pool is None:
        _token_pool = TokenPool()
        await _token_pool.initialize()
    return _token_pool

