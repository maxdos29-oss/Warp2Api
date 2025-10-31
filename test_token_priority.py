#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test token priority order"""

import asyncio
from warp2protobuf.core.token_pool import get_token_pool, TokenPriority

async def test_priority_order():
    """Test that tokens are selected in the correct priority order"""
    
    print("="*60)
    print("🧪 Testing Token Priority Order")
    print("="*60)
    
    # Get token pool
    pool = await get_token_pool()
    
    # Get pool stats
    stats = await pool.get_pool_stats()
    
    print("\n📊 Token Pool Statistics:")
    print(f"   Total tokens: {stats['total_tokens']}")
    print(f"   Active tokens: {stats['active_tokens']}")
    print(f"   Failed tokens: {stats['failed_tokens']}")
    print()
    print("   By Priority:")
    print(f"   1️⃣  Anonymous: {stats['anonymous_tokens']} (should be used first)")
    print(f"   2️⃣  Shared: {stats['shared_tokens']}")
    print(f"   3️⃣  Personal: {stats['personal_tokens']} (should be used last)")
    
    # Test token selection
    print("\n🎯 Testing Token Selection Order:")
    print("-" * 60)
    
    # Get next token multiple times to see the order
    for i in range(min(5, stats['total_tokens'])):
        token = await pool.get_next_token()
        if token:
            priority_emoji = {
                TokenPriority.ANONYMOUS: "1️⃣",
                TokenPriority.SHARED: "2️⃣",
                TokenPriority.PERSONAL: "3️⃣"
            }
            emoji = priority_emoji.get(token.priority, "❓")
            
            print(f"   Selection {i+1}: {emoji} {token.name} (Priority: {token.priority.name})")
            
            # Verify priority
            if i == 0:
                if token.priority == TokenPriority.ANONYMOUS:
                    print(f"      ✅ Correct! Anonymous token selected first")
                else:
                    print(f"      ❌ ERROR! Expected ANONYMOUS, got {token.priority.name}")
        else:
            print(f"   Selection {i+1}: ❌ No token available")
    
    # Test priority enum values
    print("\n🔢 Priority Enum Values:")
    print("-" * 60)
    for priority in TokenPriority:
        print(f"   {priority.name}: {priority.value}")
    
    # Verify order
    print("\n✅ Priority Order Verification:")
    print("-" * 60)
    anonymous_value = TokenPriority.ANONYMOUS.value
    shared_value = TokenPriority.SHARED.value
    personal_value = TokenPriority.PERSONAL.value
    
    if anonymous_value < shared_value < personal_value:
        print("   ✅ PASS: ANONYMOUS (1) < SHARED (2) < PERSONAL (3)")
        print("   ✅ Anonymous tokens will be selected first")
        print("   ✅ Personal tokens will be used as fallback")
    else:
        print(f"   ❌ FAIL: Priority values are incorrect!")
        print(f"      ANONYMOUS: {anonymous_value}")
        print(f"      SHARED: {shared_value}")
        print(f"      PERSONAL: {personal_value}")
    
    print("\n" + "="*60)
    print("✅ Test Complete")
    print("="*60)


async def test_failover():
    """Test failover behavior when a token fails"""
    
    print("\n" + "="*60)
    print("🔄 Testing Token Failover")
    print("="*60)
    
    pool = await get_token_pool()
    
    print("\n📋 Failover Scenario:")
    print("   1. Get first token (should be ANONYMOUS)")
    print("   2. Mark it as failed")
    print("   3. Get next token (should be SHARED or PERSONAL)")
    
    # Get first token
    token1 = await pool.get_next_token()
    if token1:
        print(f"\n   First token: {token1.name} ({token1.priority.name})")
        
        # Mark as failed
        await pool.mark_token_failed(token1.refresh_token)
        print(f"   ❌ Marked {token1.name} as failed")
        
        # Get next token
        token2 = await pool.get_next_token()
        if token2:
            print(f"   Next token: {token2.name} ({token2.priority.name})")
            
            if token2.priority.value > token1.priority.value:
                print(f"   ✅ Correctly failed over to lower priority token")
            elif token2.name != token1.name:
                print(f"   ✅ Correctly switched to different token")
            else:
                print(f"   ⚠️  Same token returned (might be the only one)")
        else:
            print(f"   ❌ No fallback token available")
    else:
        print(f"   ❌ No tokens available")
    
    print("\n" + "="*60)


async def main():
    """Run all tests"""
    await test_priority_order()
    await test_failover()
    
    print("\n💡 Summary:")
    print("   - Anonymous tokens are now prioritized first")
    print("   - Personal tokens are saved for when anonymous fails")
    print("   - This helps preserve personal token quota")
    print()


if __name__ == "__main__":
    asyncio.run(main())

