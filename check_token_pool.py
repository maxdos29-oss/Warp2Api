#!/usr/bin/env python3
"""检查Token Pool状态"""

import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from warp2protobuf.core.token_pool import get_token_pool


async def main():
    """检查Token Pool状态"""
    print("=" * 80)
    print("🔍 检查Token Pool状态")
    print("=" * 80)

    # 获取token pool实例
    token_pool = await get_token_pool()

    if not token_pool:
        print("❌ Token Pool未初始化")
        return
    
    # 获取统计信息
    stats = await token_pool.get_pool_stats()

    print(f"\n📊 Token Pool统计:")
    print(f"   总Token数: {stats['total_tokens']}")
    print(f"   活跃Token数: {stats['active_tokens']}")
    print(f"   失败Token数: {stats['failed_tokens']}")
    print(f"   匿名Token数: {stats['anonymous_tokens']}")
    print(f"   共享Token数: {stats['shared_tokens']}")
    print(f"   个人Token数: {stats['personal_tokens']}")
    
    print(f"\n📋 Token详情:")
    for i, token_info in enumerate(token_pool._tokens, 1):
        print(f"\n   Token #{i}:")
        print(f"      名称: {token_info.name}")
        print(f"      优先级: {token_info.priority.name} ({token_info.priority.value})")
        print(f"      活跃: {token_info.is_active}")
        print(f"      失败次数: {token_info.failure_count}")
        
        if token_info.refresh_token:
            print(f"      Refresh Token: {token_info.refresh_token[:20]}...")
        
        if token_info.last_jwt:
            print(f"      JWT: {token_info.last_jwt[:50]}...")
            if token_info.last_jwt_expiry:
                from datetime import datetime
                expiry_time = datetime.fromtimestamp(token_info.last_jwt_expiry)
                now = datetime.now()
                remaining = (expiry_time - now).total_seconds()
                print(f"      JWT过期时间: {expiry_time.strftime('%Y-%m-%d %H:%M:%S')}")
                if remaining > 0:
                    print(f"      剩余时间: {int(remaining)}秒 ({int(remaining/60)}分钟)")
                else:
                    print(f"      ⚠️ JWT已过期 ({int(-remaining)}秒前)")
    
    print("\n" + "=" * 80)
    
    # 尝试获取下一个可用Token
    print("\n🔄 尝试获取下一个可用Token...")
    try:
        token_info = await token_pool.get_next_token()
        if token_info:
            print(f"✅ 获取到Token: {token_info.token_type.name} (优先级: {token_info.priority.name})")
            
            # 尝试刷新JWT
            if token_info.refresh_token and not token_info.last_jwt:
                print(f"\n🔄 尝试刷新JWT...")
                jwt = await token_pool.get_valid_jwt(token_info)
                if jwt:
                    print(f"✅ JWT刷新成功: {jwt[:50]}...")
                else:
                    print(f"❌ JWT刷新失败")
        else:
            print("❌ 没有可用的Token")
    except Exception as e:
        print(f"❌ 获取Token失败: {e}")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(main())

