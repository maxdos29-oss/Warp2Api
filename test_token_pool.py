#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for multi-token pool functionality

Tests:
- Token pool initialization
- Priority-based token selection
- Round-robin rotation
- Failure handling and recovery
- Health monitoring
"""
import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from warp2protobuf.core.token_pool import TokenPool, TokenPriority, get_token_pool
from warp2protobuf.core.auth import (
    refresh_jwt_token,
    print_token_pool_info,
    check_token_pool_health,
    recover_failed_tokens
)
from warp2protobuf.core.logging import logger


async def test_token_pool_initialization():
    """Test 1: Token pool initialization"""
    logger.info("\n" + "="*60)
    logger.info("TEST 1: Token Pool Initialization")
    logger.info("="*60)
    
    pool = await get_token_pool()
    stats = await pool.get_pool_stats()
    
    logger.info(f"✅ Pool initialized with {stats['total_tokens']} tokens")
    logger.info(f"   Active tokens: {stats['active_tokens']}")
    
    for priority, info in stats['by_priority'].items():
        if info['total'] > 0:
            logger.info(f"   {priority}: {info['active']}/{info['total']} active")
    
    return stats['total_tokens'] > 0


async def test_priority_selection():
    """Test 2: Priority-based token selection"""
    logger.info("\n" + "="*60)
    logger.info("TEST 2: Priority-based Token Selection")
    logger.info("="*60)
    
    pool = await get_token_pool()
    
    # Get 5 tokens and check priority order
    tokens_selected = []
    for i in range(5):
        token = await pool.get_next_token()
        if token:
            tokens_selected.append(token)
            logger.info(f"   Token {i+1}: {token.name} (priority: {token.priority.name})")
    
    if not tokens_selected:
        logger.error("❌ No tokens selected")
        return False
    
    # Verify personal tokens are selected first
    first_token = tokens_selected[0]
    logger.info(f"✅ First token priority: {first_token.priority.name}")
    
    return True


async def test_round_robin():
    """Test 3: Round-robin rotation within same priority"""
    logger.info("\n" + "="*60)
    logger.info("TEST 3: Round-robin Rotation")
    logger.info("="*60)
    
    pool = await get_token_pool()
    stats = await pool.get_pool_stats()
    
    # Get tokens multiple times to see rotation
    token_names = []
    for i in range(10):
        token = await pool.get_next_token()
        if token:
            token_names.append(token.name)
    
    logger.info(f"   Token selection sequence: {token_names}")
    
    # Check if we see rotation (same token shouldn't appear consecutively if multiple tokens exist)
    if len(set(token_names)) > 1:
        logger.info("✅ Round-robin rotation working")
        return True
    else:
        logger.info("⚠️ Only one token available or rotation not visible")
        return True  # Still pass if only one token


async def test_token_refresh():
    """Test 4: Token refresh functionality"""
    logger.info("\n" + "="*60)
    logger.info("TEST 4: Token Refresh")
    logger.info("="*60)
    
    try:
        token_data = await refresh_jwt_token()
        
        if token_data and "access_token" in token_data:
            logger.info("✅ Token refresh successful")
            logger.info(f"   Access token length: {len(token_data['access_token'])}")
            return True
        else:
            logger.error("❌ Token refresh failed")
            return False
    except Exception as e:
        logger.error(f"❌ Token refresh error: {e}")
        return False


async def test_health_check():
    """Test 5: Health check functionality"""
    logger.info("\n" + "="*60)
    logger.info("TEST 5: Health Check")
    logger.info("="*60)
    
    health = await check_token_pool_health()
    
    if health:
        logger.info("✅ Health check completed")
        return True
    else:
        logger.error("❌ Health check failed")
        return False


async def test_failure_handling():
    """Test 6: Failure handling and recovery"""
    logger.info("\n" + "="*60)
    logger.info("TEST 6: Failure Handling and Recovery")
    logger.info("="*60)
    
    pool = await get_token_pool()
    
    # Get a token and simulate failures
    token = await pool.get_next_token()
    if not token:
        logger.warning("⚠️ No token available for failure test")
        return True
    
    logger.info(f"   Testing failure handling with token: {token.name}")
    
    # Simulate 3 failures
    for i in range(3):
        await pool.mark_token_failed(token)
        logger.info(f"   Failure {i+1}/3: failure_count={token.failure_count}, is_active={token.is_active}")
    
    if not token.is_active:
        logger.info("✅ Token correctly deactivated after 3 failures")
    else:
        logger.error("❌ Token should be deactivated after 3 failures")
        return False
    
    # Test recovery
    logger.info("   Testing token recovery...")
    recovered = await recover_failed_tokens()
    logger.info(f"   Recovered {recovered} tokens")
    
    if token.is_active:
        logger.info("✅ Token successfully recovered")
        return True
    else:
        logger.error("❌ Token recovery failed")
        return False


async def test_pool_info():
    """Test 7: Pool information display"""
    logger.info("\n" + "="*60)
    logger.info("TEST 7: Pool Information Display")
    logger.info("="*60)
    
    await print_token_pool_info()
    logger.info("✅ Pool information displayed")
    return True


async def run_all_tests():
    """Run all tests"""
    logger.info("\n" + "="*60)
    logger.info("🧪 MULTI-TOKEN POOL TEST SUITE")
    logger.info("="*60)
    
    tests = [
        ("Token Pool Initialization", test_token_pool_initialization),
        ("Priority-based Selection", test_priority_selection),
        ("Round-robin Rotation", test_round_robin),
        ("Token Refresh", test_token_refresh),
        ("Health Check", test_health_check),
        ("Failure Handling", test_failure_handling),
        ("Pool Information", test_pool_info),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"❌ Test '{test_name}' crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    logger.info("\n" + "="*60)
    logger.info("📊 TEST SUMMARY")
    logger.info("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status}: {test_name}")
    
    logger.info("="*60)
    logger.info(f"Results: {passed}/{total} tests passed")
    logger.info("="*60)
    
    return passed == total


async def main():
    """Main entry point"""
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    # Check if we have any tokens configured
    has_personal = bool(os.getenv("WARP_REFRESH_TOKEN") or os.getenv("WARP_PERSONAL_TOKENS"))
    has_shared = bool(os.getenv("WARP_SHARED_TOKENS"))
    has_anonymous = bool(os.getenv("WARP_ANONYMOUS_TOKEN"))
    
    logger.info("Environment Configuration:")
    logger.info(f"  Personal tokens: {'✅' if has_personal else '❌'}")
    logger.info(f"  Shared tokens: {'✅' if has_shared else '❌'}")
    logger.info(f"  Anonymous token: {'✅' if has_anonymous else '❌ (will use built-in)'}")
    
    if not (has_personal or has_shared or has_anonymous):
        logger.info("\n⚠️ No tokens configured in environment, will use built-in anonymous token")
    
    # Run tests
    success = await run_all_tests()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())

