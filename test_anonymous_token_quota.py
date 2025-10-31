#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
匿名Token配额测试

测试匿名Token的配额限制，找出429错误的原因
"""
import asyncio
import json
import httpx
from typing import Dict, Any, Optional

from warp2protobuf.core.logging import logger
from warp2protobuf.core.auth import acquire_anonymous_access_token


async def test_anonymous_token_quota():
    """
    测试匿名Token的配额限制
    
    目标：
    1. 创建一个新的匿名Token
    2. 使用这个Token发送多个请求
    3. 观察何时遇到429错误
    4. 分析配额限制
    """
    print("=" * 80)
    print("🧪 测试匿名Token配额限制")
    print("=" * 80)
    
    # 步骤1: 获取一个新的匿名Token
    print("\n📝 步骤1: 获取新的匿名Token")
    try:
        access_token = await acquire_anonymous_access_token()
        if not access_token:
            print("❌ 无法获取匿名Token")
            return False
        
        print(f"✅ 成功获取匿名Token")
        print(f"   Token长度: {len(access_token)} 字符")
        print(f"   Token前缀: {access_token[:50]}...")
    except Exception as e:
        print(f"❌ 获取匿名Token失败: {e}")
        return False
    
    # 步骤2: 使用这个Token发送测试请求
    print("\n📝 步骤2: 使用匿名Token发送测试请求")
    
    # 准备测试请求（使用简单的protobuf测试数据）
    # 这是一个最小的有效protobuf请求
    protobuf_data = bytes.fromhex('0a26122463613264313833632d386263622d343936372d383031632d393561633162323030313030')
    print(f"✅ 使用测试protobuf数据: {len(protobuf_data)} 字节")
    
    # 步骤3: 连续发送请求，直到遇到429错误
    print("\n📝 步骤3: 连续发送请求，观察配额限制")
    
    url = "https://app.warp.dev/ai/multi-agent"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/x-protobuf",
        "Accept": "text/event-stream",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    
    success_count = 0
    error_count = 0
    quota_exhausted = False
    
    async with httpx.AsyncClient(timeout=30.0, http2=True) as client:
        for i in range(20):  # 最多测试20次
            try:
                print(f"\n🔄 请求 #{i+1}:")
                
                response = await client.post(url, headers=headers, content=protobuf_data)
                
                print(f"   状态码: {response.status_code}")
                
                if response.status_code == 200:
                    success_count += 1
                    print(f"   ✅ 成功 (总成功: {success_count})")
                    
                elif response.status_code == 429:
                    error_count += 1
                    quota_exhausted = True
                    
                    # 解析错误信息
                    try:
                        error_data = response.json()
                        error_msg = error_data.get("error", "Unknown error")
                        print(f"   ❌ 429错误: {error_msg}")
                    except:
                        print(f"   ❌ 429错误: {response.text[:200]}")
                    
                    print(f"\n📊 配额统计:")
                    print(f"   成功请求数: {success_count}")
                    print(f"   失败请求数: {error_count}")
                    print(f"   配额用尽位置: 第 {i+1} 次请求")
                    
                    # 检查响应头中的配额信息
                    print(f"\n📋 响应头信息:")
                    for key, value in response.headers.items():
                        if any(keyword in key.lower() for keyword in ['rate', 'limit', 'quota', 'retry']):
                            print(f"   {key}: {value}")
                    
                    break
                    
                elif response.status_code == 401:
                    print(f"   ❌ 401错误: Token无效或过期")
                    print(f"   响应: {response.text[:200]}")
                    break
                    
                elif response.status_code == 500:
                    error_count += 1
                    print(f"   ❌ 500错误: 服务器内部错误")
                    print(f"   响应: {response.text[:200]}")
                    
                else:
                    error_count += 1
                    print(f"   ❌ {response.status_code}错误")
                    print(f"   响应: {response.text[:200]}")
                
                # 短暂延迟，避免请求过快
                await asyncio.sleep(0.5)
                
            except Exception as e:
                error_count += 1
                print(f"   ❌ 请求异常: {e}")
                break
    
    # 步骤4: 总结
    print("\n" + "=" * 80)
    print("📊 测试结果总结")
    print("=" * 80)
    print(f"总请求数: {success_count + error_count}")
    print(f"成功请求数: {success_count}")
    print(f"失败请求数: {error_count}")
    
    if quota_exhausted:
        print(f"\n🎯 配额限制分析:")
        print(f"   匿名Token在 {success_count} 次成功请求后配额用尽")
        print(f"   这说明每个匿名Token的配额非常有限")
    else:
        print(f"\n⚠️ 未遇到配额限制（可能是其他错误）")
    
    return True


async def test_builtin_anonymous_token():
    """
    测试内置的匿名Token配额
    """
    print("\n" + "=" * 80)
    print("🧪 测试内置匿名Token的配额状态")
    print("=" * 80)
    
    # 从token pool获取内置的匿名token
    from warp2protobuf.core.token_pool import get_token_pool
    
    pool = await get_token_pool()
    stats = await pool.get_pool_stats()
    
    print(f"\n📊 Token Pool状态:")
    print(f"   总Token数: {stats['total_tokens']}")
    print(f"   匿名Token数: {stats['anonymous_tokens']}")
    print(f"   个人Token数: {stats['personal_tokens']}")
    
    # 获取匿名token
    anonymous_token = None
    for token_info in pool._tokens:
        if token_info.priority.name == "ANONYMOUS":
            anonymous_token = token_info
            break
    
    if not anonymous_token:
        print("❌ 未找到匿名Token")
        return False
    
    print(f"\n📝 内置匿名Token信息:")
    print(f"   名称: {anonymous_token.name}")
    print(f"   优先级: {anonymous_token.priority.name}")
    print(f"   Refresh Token: {anonymous_token.refresh_token[:50]}...")
    print(f"   最后使用时间: {anonymous_token.last_used}")
    print(f"   失败次数: {anonymous_token.failure_count}")
    print(f"   是否活跃: {anonymous_token.is_active}")
    
    # 尝试刷新这个token
    print(f"\n🔄 尝试刷新内置匿名Token...")
    from warp2protobuf.core.auth import refresh_jwt_token_with_token_info
    
    try:
        token_data = await refresh_jwt_token_with_token_info(anonymous_token)
        if token_data and "access_token" in token_data:
            access_token = token_data["access_token"]
            print(f"✅ Token刷新成功")
            print(f"   Access Token长度: {len(access_token)} 字符")
            
            # 尝试发送一个测试请求
            print(f"\n🔄 使用刷新后的Token发送测试请求...")
            
            url = "https://app.warp.dev/ai/multi-agent"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/x-protobuf",
                "Accept": "text/event-stream",
            }
            
            # 简单的测试数据
            test_data = b'\x0a\x26\x12\x24test-builtin-token'
            
            async with httpx.AsyncClient(timeout=30.0, http2=True) as client:
                response = await client.post(url, headers=headers, content=test_data)
                
                print(f"   状态码: {response.status_code}")
                
                if response.status_code == 200:
                    print(f"   ✅ 请求成功！内置匿名Token仍有配额")
                elif response.status_code == 429:
                    try:
                        error_data = response.json()
                        error_msg = error_data.get("error", "Unknown error")
                        print(f"   ❌ 429错误: {error_msg}")
                        print(f"   ⚠️ 内置匿名Token配额已用尽")
                    except:
                        print(f"   ❌ 429错误: {response.text[:200]}")
                else:
                    print(f"   ❌ {response.status_code}错误: {response.text[:200]}")
        else:
            print(f"❌ Token刷新失败")
    except Exception as e:
        print(f"❌ Token刷新异常: {e}")
        import traceback
        traceback.print_exc()
    
    return True


async def main():
    """运行所有测试"""
    print("🚀 开始匿名Token配额测试")
    print("=" * 80)
    print("测试目标: 找出匿名Token 429错误的原因")
    print("=" * 80)
    
    # 测试1: 测试新申请的匿名Token配额
    await test_anonymous_token_quota()
    
    # 测试2: 测试内置匿名Token的配额状态
    await test_builtin_anonymous_token()
    
    print("\n" + "=" * 80)
    print("🎯 结论")
    print("=" * 80)
    print("匿名Token 429错误的可能原因:")
    print("1. 每个匿名Token的配额非常有限（可能只有几次请求）")
    print("2. 匿名Token可能有时间限制（例如每小时重置）")
    print("3. Warp可能对匿名Token有更严格的速率限制")
    print("4. 内置的匿名Token可能已经被大量使用，配额耗尽")


if __name__ == "__main__":
    asyncio.run(main())

