#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Multi-Token Demo Script

Demonstrates the multi-token functionality with interactive examples.
"""
import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from warp2protobuf.core.token_pool import get_token_pool, TokenPriority
from warp2protobuf.core.auth import (
    refresh_jwt_token,
    print_token_pool_info,
    check_token_pool_health,
)
from warp2protobuf.core.logging import logger


def print_banner(text):
    """Print a formatted banner"""
    width = 60
    print("\n" + "=" * width)
    print(f"  {text}")
    print("=" * width + "\n")


async def demo_initialization():
    """Demo 1: Token pool initialization"""
    print_banner("Demo 1: Token Pool Initialization")
    
    print("📝 Loading tokens from environment variables...")
    print("   - WARP_REFRESH_TOKEN")
    print("   - WARP_PERSONAL_TOKENS")
    print("   - WARP_SHARED_TOKENS")
    print("   - WARP_ANONYMOUS_TOKEN")
    print()
    
    pool = await get_token_pool()
    stats = await pool.get_pool_stats()
    
    print(f"✅ Token pool initialized!")
    print(f"   Total tokens: {stats['total_tokens']}")
    print(f"   Active tokens: {stats['active_tokens']}")
    print()
    
    for priority, info in stats['by_priority'].items():
        if info['total'] > 0:
            print(f"   {priority}:")
            print(f"     - Total: {info['total']}")
            print(f"     - Active: {info['active']}")
            print(f"     - Inactive: {info['inactive']}")
    
    input("\n按Enter继续...")


async def demo_priority_selection():
    """Demo 2: Priority-based token selection"""
    print_banner("Demo 2: Priority-based Token Selection")
    
    print("🎯 Token selection follows priority order:")
    print("   1. PERSONAL (个人token) - 最高优先级")
    print("   2. SHARED (共享token) - 中等优先级")
    print("   3. ANONYMOUS (匿名token) - 最低优先级")
    print()
    
    pool = await get_token_pool()
    
    print("📊 Selecting 5 tokens to demonstrate priority:")
    for i in range(5):
        token = await pool.get_next_token()
        if token:
            priority_emoji = {
                TokenPriority.PERSONAL: "🔑",
                TokenPriority.SHARED: "👥",
                TokenPriority.ANONYMOUS: "🌐"
            }
            emoji = priority_emoji.get(token.priority, "❓")
            print(f"   Token {i+1}: {emoji} {token.name} (priority: {token.priority.name})")
    
    input("\n按Enter继续...")


async def demo_token_refresh():
    """Demo 3: Token refresh with automatic failover"""
    print_banner("Demo 3: Token Refresh with Failover")
    
    print("🔄 Attempting to refresh JWT token...")
    print("   The system will:")
    print("   1. Select a token from the pool (by priority)")
    print("   2. Try to refresh JWT with that token")
    print("   3. If failed, automatically try the next token")
    print("   4. Continue until success or all tokens exhausted")
    print()
    
    token_data = await refresh_jwt_token()
    
    if token_data and "access_token" in token_data:
        jwt = token_data["access_token"]
        print(f"✅ JWT refresh successful!")
        print(f"   Access token length: {len(jwt)} characters")
        print(f"   Token preview: {jwt[:50]}...")
    else:
        print("❌ JWT refresh failed")
    
    input("\n按Enter继续...")


async def demo_health_check():
    """Demo 4: Health check and monitoring"""
    print_banner("Demo 4: Health Check and Monitoring")
    
    print("🏥 Performing health check on all tokens...")
    print()
    
    health = await check_token_pool_health()
    
    print(f"📊 Health Summary:")
    print(f"   Healthy tokens: {health['healthy_tokens']}/{health['total_tokens']}")
    print(f"   Unhealthy tokens: {health['unhealthy_tokens']}")
    print()
    
    print("📋 Detailed Token Status:")
    for token_status in health['tokens']:
        status_icon = "✅" if token_status['is_healthy'] else "❌"
        priority_emoji = {
            "PERSONAL": "🔑",
            "SHARED": "👥",
            "ANONYMOUS": "🌐"
        }
        emoji = priority_emoji.get(token_status['priority'], "❓")
        
        print(f"   {status_icon} {emoji} {token_status['name']}")
        print(f"      Priority: {token_status['priority']}")
        print(f"      Active: {token_status['is_active']}")
        print(f"      Failures: {token_status['failure_count']}/3")
        
        if token_status.get('jwt_expires_in'):
            expires_hours = token_status['jwt_expires_in'] / 3600
            print(f"      JWT expires in: {expires_hours:.1f} hours")
        print()
    
    input("\n按Enter继续...")


async def demo_pool_info():
    """Demo 5: Display pool information"""
    print_banner("Demo 5: Token Pool Information")
    
    print("📊 Displaying complete token pool information...")
    print()
    
    await print_token_pool_info()
    
    input("\n按Enter继续...")


async def demo_configuration_examples():
    """Demo 6: Configuration examples"""
    print_banner("Demo 6: Configuration Examples")
    
    print("📝 Here are some configuration examples:\n")
    
    print("1️⃣  Single Personal Token (Simplest)")
    print("   .env:")
    print("   WARP_REFRESH_TOKEN=your_personal_token")
    print()
    
    print("2️⃣  Multiple Personal Tokens (Recommended)")
    print("   .env:")
    print("   WARP_REFRESH_TOKEN=token_1")
    print("   WARP_PERSONAL_TOKENS=token_2,token_3,token_4")
    print()
    
    print("3️⃣  Full Configuration (Best Practice)")
    print("   .env:")
    print("   # Personal tokens (highest priority)")
    print("   WARP_REFRESH_TOKEN=my_personal_token")
    print("   WARP_PERSONAL_TOKENS=personal_2,personal_3")
    print()
    print("   # Shared tokens (medium priority)")
    print("   WARP_SHARED_TOKENS=team_1,team_2,team_3")
    print()
    print("   # Anonymous token (lowest priority)")
    print("   WARP_ANONYMOUS_TOKEN=anonymous_fallback")
    print()
    
    input("\n按Enter继续...")


async def demo_current_config():
    """Demo 7: Show current configuration"""
    print_banner("Demo 7: Current Configuration")
    
    print("🔍 Checking your current configuration...\n")
    
    has_personal = bool(os.getenv("WARP_REFRESH_TOKEN") or os.getenv("WARP_PERSONAL_TOKENS"))
    has_shared = bool(os.getenv("WARP_SHARED_TOKENS"))
    has_anonymous = bool(os.getenv("WARP_ANONYMOUS_TOKEN"))
    
    print("Environment Variables:")
    print(f"   WARP_REFRESH_TOKEN: {'✅ Set' if os.getenv('WARP_REFRESH_TOKEN') else '❌ Not set'}")
    print(f"   WARP_PERSONAL_TOKENS: {'✅ Set' if os.getenv('WARP_PERSONAL_TOKENS') else '❌ Not set'}")
    print(f"   WARP_SHARED_TOKENS: {'✅ Set' if os.getenv('WARP_SHARED_TOKENS') else '❌ Not set'}")
    print(f"   WARP_ANONYMOUS_TOKEN: {'✅ Set' if os.getenv('WARP_ANONYMOUS_TOKEN') else '❌ Not set (will use built-in)'}")
    print()
    
    print("Token Types Available:")
    print(f"   Personal tokens: {'✅' if has_personal else '❌'}")
    print(f"   Shared tokens: {'✅' if has_shared else '❌'}")
    print(f"   Anonymous token: {'✅' if has_anonymous else '✅ (built-in)'}")
    print()
    
    if not (has_personal or has_shared):
        print("💡 Tip: Configure personal or shared tokens for better performance!")
        print("   See .env.multi-token.example for configuration examples.")
    
    input("\n按Enter继续...")


async def main():
    """Main demo entry point"""
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    print("\n" + "=" * 60)
    print("  🎉 Warp2Api Multi-Token Demo")
    print("=" * 60)
    print()
    print("This demo will show you how the multi-token functionality works.")
    print("You can configure multiple refresh tokens with different priorities.")
    print()
    input("按Enter开始演示...")
    
    demos = [
        demo_initialization,
        demo_priority_selection,
        demo_token_refresh,
        demo_health_check,
        demo_pool_info,
        demo_configuration_examples,
        demo_current_config,
    ]
    
    for demo in demos:
        try:
            await demo()
        except KeyboardInterrupt:
            print("\n\n👋 Demo interrupted by user")
            break
        except Exception as e:
            print(f"\n❌ Error in demo: {e}")
            import traceback
            traceback.print_exc()
    
    print_banner("Demo Complete!")
    print("✅ All demos completed successfully!")
    print()
    print("📚 For more information:")
    print("   - README.md - Quick start guide")
    print("   - docs/MULTI_TOKEN_GUIDE.md - Detailed guide")
    print("   - .env.multi-token.example - Configuration examples")
    print("   - test_token_pool.py - Test suite")
    print()
    print("🚀 Start using multi-token configuration today!")
    print()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
        sys.exit(0)

