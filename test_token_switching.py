#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Token切换功能测试用例

测试Token Pool在429错误时的自动切换功能
"""
import asyncio
import json
import time
from typing import Dict, Any

from warp2protobuf.core.token_pool import get_token_pool, TokenPriority
from warp2protobuf.core.logging import logger


async def test_token_pool_basic():
    """测试Token Pool基本功能"""
    print("=" * 60)
    print("🧪 测试1: Token Pool基本功能")
    print("=" * 60)
    
    try:
        # 获取token pool
        pool = await get_token_pool()
        
        # 显示pool状态
        stats = await pool.get_pool_stats()
        print(f"📊 Token Pool状态:")
        print(f"   总Token数: {stats['total_tokens']}")
        print(f"   活跃Token数: {stats['active_tokens']}")
        print(f"   失败Token数: {stats['failed_tokens']}")
        print(f"   匿名Token数: {stats['anonymous_tokens']}")
        print(f"   个人Token数: {stats['personal_tokens']}")
        
        # 测试获取token
        print(f"\n🎯 测试获取token:")
        for i in range(3):
            token_info = await pool.get_next_token()
            if token_info:
                print(f"   第{i+1}次: {token_info.name} (优先级: {token_info.priority.name})")
            else:
                print(f"   第{i+1}次: None")
        
        print("✅ Token Pool基本功能测试通过")
        return True
        
    except Exception as e:
        print(f"❌ Token Pool基本功能测试失败: {e}")
        return False


async def test_token_exclusion():
    """测试Token排除功能"""
    print("\n" + "=" * 60)
    print("🧪 测试2: Token排除功能")
    print("=" * 60)
    
    try:
        pool = await get_token_pool()
        
        # 获取第一个token
        first_token = await pool.get_next_token()
        if not first_token:
            print("❌ 无法获取第一个token")
            return False
            
        print(f"🎯 第一个token: {first_token.name} (优先级: {first_token.priority.name})")
        
        # 排除第一个token，获取下一个
        print(f"🔄 排除 {first_token.refresh_token[:20]}... 获取下一个token")
        second_token = await pool.get_next_token_excluding(first_token.refresh_token)
        
        if second_token:
            print(f"✅ 获取到不同的token: {second_token.name} (优先级: {second_token.priority.name})")
            if second_token.refresh_token == first_token.refresh_token:
                print("❌ 错误：获取到了相同的token")
                return False
        else:
            print("⚠️ 没有其他可用token（这可能是正常的，如果只有一个token）")
        
        print("✅ Token排除功能测试通过")
        return True
        
    except Exception as e:
        print(f"❌ Token排除功能测试失败: {e}")
        return False


async def test_token_priority():
    """测试Token优先级"""
    print("\n" + "=" * 60)
    print("🧪 测试3: Token优先级")
    print("=" * 60)
    
    try:
        pool = await get_token_pool()
        
        # 获取多个token，检查优先级
        print("🎯 连续获取token，检查优先级:")
        priorities_seen = []
        
        for i in range(5):
            token_info = await pool.get_next_token()
            if token_info:
                priorities_seen.append(token_info.priority)
                print(f"   第{i+1}次: {token_info.name} (优先级: {token_info.priority.name}, 值: {token_info.priority.value})")
        
        # 检查是否优先使用匿名token
        if priorities_seen:
            first_priority = priorities_seen[0]
            if first_priority == TokenPriority.ANONYMOUS:
                print("✅ 正确：优先使用匿名Token")
            else:
                print(f"⚠️ 注意：第一个token不是匿名Token，而是 {first_priority.name}")
        
        print("✅ Token优先级测试通过")
        return True
        
    except Exception as e:
        print(f"❌ Token优先级测试失败: {e}")
        return False


async def test_last_used_detection():
    """测试最后使用token检测"""
    print("\n" + "=" * 60)
    print("🧪 测试4: 最后使用Token检测")
    print("=" * 60)
    
    try:
        pool = await get_token_pool()
        
        # 获取一个token并标记为已使用
        token_info = await pool.get_next_token()
        if not token_info:
            print("❌ 无法获取token")
            return False
            
        print(f"🎯 使用token: {token_info.name}")
        
        # 等待一小段时间，然后检测最后使用的token
        await asyncio.sleep(0.1)
        
        last_used = pool.get_last_used_token()
        if last_used:
            print(f"✅ 检测到最后使用的token: {last_used.name} (last_used: {last_used.last_used})")
            if last_used.refresh_token == token_info.refresh_token:
                print("✅ 正确：检测到的token与使用的token一致")
            else:
                print("❌ 错误：检测到的token与使用的token不一致")
                return False
        else:
            print("❌ 无法检测到最后使用的token")
            return False
        
        print("✅ 最后使用Token检测测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 最后使用Token检测测试失败: {e}")
        return False


async def simulate_429_error_handling():
    """模拟429错误处理流程"""
    print("\n" + "=" * 60)
    print("🧪 测试5: 模拟429错误处理流程")
    print("=" * 60)
    
    try:
        pool = await get_token_pool()
        
        # 模拟第一次请求使用匿名token
        print("📝 模拟场景：匿名Token配额用尽，需要切换到个人Token")
        
        # 1. 获取匿名token（模拟第一次请求）
        first_token = await pool.get_next_token()
        if not first_token:
            print("❌ 无法获取第一个token")
            return False
            
        print(f"🎯 第一次请求使用: {first_token.name} (优先级: {first_token.priority.name})")
        
        # 2. 模拟429错误，需要切换token
        print("❌ 模拟收到429错误: No remaining quota")
        
        # 3. 检测当前使用的token
        last_used = pool.get_last_used_token()
        if last_used:
            current_token_refresh = last_used.refresh_token
            print(f"🔍 检测到当前使用的token: {last_used.name}")
        else:
            current_token_refresh = first_token.refresh_token
            print(f"🔍 使用第一次请求的token作为当前token: {first_token.name}")
        
        # 4. 获取下一个可用token（排除当前失败的token）
        print(f"🔄 尝试获取下一个token (排除: {current_token_refresh[:20]}...)")
        next_token = await pool.get_next_token_excluding(current_token_refresh)
        
        if next_token:
            print(f"✅ 成功获取下一个token: {next_token.name} (优先级: {next_token.priority.name})")
            if next_token.refresh_token != current_token_refresh:
                print("✅ 正确：获取到了不同的token")
            else:
                print("❌ 错误：获取到了相同的token")
                return False
        else:
            print("⚠️ 没有其他可用token，需要申请新的匿名token")
        
        print("✅ 429错误处理流程测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 429错误处理流程测试失败: {e}")
        return False


async def main():
    """运行所有测试"""
    print("🚀 开始Token切换功能测试")
    print("=" * 80)
    
    tests = [
        test_token_pool_basic,
        test_token_exclusion,
        test_token_priority,
        test_last_used_detection,
        simulate_429_error_handling,
    ]
    
    passed = 0
    total = len(tests)
    
    for test_func in tests:
        try:
            result = await test_func()
            if result:
                passed += 1
        except Exception as e:
            print(f"❌ 测试 {test_func.__name__} 异常: {e}")
    
    print("\n" + "=" * 80)
    print("📊 测试结果总结")
    print("=" * 80)
    print(f"✅ 通过: {passed}/{total}")
    print(f"❌ 失败: {total - passed}/{total}")
    
    if passed == total:
        print("🎉 所有测试通过！Token切换功能正常工作")
    else:
        print("⚠️ 部分测试失败，需要检查Token切换功能")
    
    return passed == total


if __name__ == "__main__":
    asyncio.run(main())
