#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
综合测试Warp API的限制情况

测试目标：
1. 匿名Token的配额限制
2. 个人Token的可用性
3. 创建匿名用户的速率限制
4. 不同Token类型的行为差异
"""
import asyncio
import httpx
import os
import time
from dotenv import load_dotenv

load_dotenv()


async def test_anonymous_token_creation():
    """测试匿名Token创建的限制"""
    print("=" * 80)
    print("🧪 测试1: 匿名Token创建限制")
    print("=" * 80)
    
    url = "https://app.warp.dev/graphql/v2?op=CreateAnonymousUser"
    
    query = """
mutation CreateAnonymousUser($input: CreateAnonymousUserInput!, $requestContext: RequestContext!) {
  createAnonymousUser(input: $input, requestContext: $requestContext) {
    __typename
    ... on CreateAnonymousUserOutput {
      expiresAt
      anonymousUserType
      firebaseUid
      idToken
      isInviteValid
      responseContext { serverVersion }
    }
    ... on UserFacingError {
      error { __typename message }
      responseContext { serverVersion }
    }
  }
}
"""
    
    variables = {
        "input": {
            "anonymousUserType": "NATIVE_CLIENT_ANONYMOUS_USER_FEATURE_GATED",
            "expirationType": "NO_EXPIRATION",
            "referralCode": None
        },
        "requestContext": {
            "clientContext": {"version": "v0.2025.10.29.08.12.stable_01"},
            "osContext": {
                "category": "WINDOWS",
                "linuxKernelVersion": None,
                "name": "Windows",
                "version": "10.0.22631"
            }
        }
    }
    
    headers = {
        "content-type": "application/json",
        "x-warp-client-version": "v0.2025.10.29.08.12.stable_01",
        "x-warp-os-category": "WINDOWS",
        "x-warp-os-name": "Windows",
        "x-warp-os-version": "10.0.22631",
    }
    
    # 尝试连续创建3次
    results = []
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for i in range(3):
            print(f"\n📝 尝试 #{i+1}: 创建匿名用户")
            
            try:
                response = await client.post(
                    url,
                    json={"query": query, "variables": variables, "operationName": "CreateAnonymousUser"},
                    headers=headers
                )
                
                print(f"   状态码: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    if "data" in data and "createAnonymousUser" in data["data"]:
                        firebase_uid = data["data"]["createAnonymousUser"].get("firebaseUid")
                        print(f"   ✅ 成功创建匿名用户: {firebase_uid}")
                        results.append(("success", firebase_uid))
                    else:
                        print(f"   ❌ 响应格式异常: {data}")
                        results.append(("error", "invalid_response"))
                        
                elif response.status_code == 429:
                    print(f"   ❌ 429错误: 速率限制")
                    results.append(("rate_limit", None))
                    
                else:
                    print(f"   ❌ {response.status_code}错误: {response.text[:100]}")
                    results.append(("error", response.status_code))
                
            except Exception as e:
                print(f"   ❌ 异常: {e}")
                results.append(("exception", str(e)))
            
            # 短暂延迟
            if i < 2:
                await asyncio.sleep(2)
    
    # 分析结果
    print(f"\n📊 创建匿名用户测试结果:")
    success_count = sum(1 for r in results if r[0] == "success")
    rate_limit_count = sum(1 for r in results if r[0] == "rate_limit")
    
    print(f"   成功: {success_count}/3")
    print(f"   速率限制: {rate_limit_count}/3")
    
    if rate_limit_count > 0:
        print(f"\n   ⚠️ 结论: Warp限制了匿名用户创建频率")
    else:
        print(f"\n   ✅ 结论: 可以正常创建匿名用户")
    
    return results


async def test_anonymous_token_quota():
    """测试匿名Token的配额限制"""
    print("\n" + "=" * 80)
    print("🧪 测试2: 匿名Token配额限制")
    print("=" * 80)
    
    # 使用内置的匿名Token
    from warp2protobuf.core.token_pool import get_token_pool
    
    pool = await get_token_pool()
    
    # 获取匿名token
    anonymous_token = None
    for token_info in pool._tokens:
        if token_info.priority.name == "ANONYMOUS":
            anonymous_token = token_info
            break
    
    if not anonymous_token:
        print("❌ 未找到匿名Token")
        return None
    
    print(f"📝 使用内置匿名Token: {anonymous_token.name}")
    
    # 刷新获取Access Token
    from warp2protobuf.core.auth import refresh_jwt_token_with_token_info
    
    try:
        token_data = await refresh_jwt_token_with_token_info(anonymous_token)
        if not token_data or "access_token" not in token_data:
            print("❌ Token刷新失败")
            return None
        
        access_token = token_data["access_token"]
        print(f"✅ Token刷新成功")
        
    except Exception as e:
        print(f"❌ Token刷新异常: {e}")
        return None
    
    # 发送测试请求
    url = "https://app.warp.dev/ai/multi-agent"
    test_data = bytes.fromhex('0a26122463613264313833632d386263622d343936372d383031632d393561633162323030313030')
    
    headers = {
        "accept": "text/event-stream",
        "content-type": "application/x-protobuf",
        "x-warp-client-version": "v0.2025.08.06.08.12.stable_02",
        "x-warp-os-category": "Windows",
        "x-warp-os-name": "Windows",
        "x-warp-os-version": "11 (26100)",
        "authorization": f"Bearer {access_token}",
        "content-length": str(len(test_data)),
    }
    
    async with httpx.AsyncClient(timeout=30.0, http2=True) as client:
        response = await client.post(url, headers=headers, content=test_data)
        
        print(f"\n📥 响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            print(f"   ✅ 匿名Token仍有配额")
            return "has_quota"
        elif response.status_code == 429:
            try:
                error_data = response.json()
                error_msg = error_data.get("error", "Unknown")
                print(f"   ❌ 429错误: {error_msg}")
                
                if "No remaining quota" in error_msg:
                    print(f"\n   ⚠️ 结论: 匿名Token配额已用尽")
                    return "quota_exhausted"
            except:
                print(f"   ❌ 429错误: {response.text[:100]}")
        elif response.status_code == 500:
            print(f"   ❌ 500错误: 服务器内部错误")
            return "server_error"
        else:
            print(f"   ❌ {response.status_code}错误")
            return f"error_{response.status_code}"


async def test_personal_token_status():
    """测试个人Token的状态"""
    print("\n" + "=" * 80)
    print("🧪 测试3: 个人Token状态")
    print("=" * 80)
    
    refresh_token = os.getenv("WARP_REFRESH_TOKEN")
    if not refresh_token:
        print("❌ 未找到个人Token")
        return None
    
    print(f"📝 个人Refresh Token: {refresh_token[:50]}...")
    
    # 步骤1: 测试Token刷新
    print(f"\n📝 步骤1: 测试Token刷新")
    
    refresh_url = "https://securetoken.googleapis.com/v1/token?key=AIzaSyBdy3O3S9hrdayLJxJ7mriBR4qgUaUygAs"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                refresh_url,
                json={"grant_type": "refresh_token", "refresh_token": refresh_token}
            )
            
            print(f"   状态码: {response.status_code}")
            
            if response.status_code == 200:
                token_data = response.json()
                access_token = token_data.get("access_token")
                user_id = token_data.get("user_id")
                
                print(f"   ✅ Token刷新成功")
                print(f"   User ID: {user_id}")
                
            elif response.status_code == 400:
                error_data = response.json()
                print(f"   ❌ 400错误: {error_data}")
                print(f"\n   ⚠️ 结论: 个人Token无效或已过期")
                return "invalid_token"
                
            else:
                print(f"   ❌ {response.status_code}错误: {response.text[:100]}")
                return f"refresh_error_{response.status_code}"
                
        except Exception as e:
            print(f"   ❌ 异常: {e}")
            return "exception"
    
    # 步骤2: 测试AI请求
    print(f"\n📝 步骤2: 测试AI请求")
    
    url = "https://app.warp.dev/ai/multi-agent"
    test_data = bytes.fromhex('0a26122463613264313833632d386263622d343936372d383031632d393561633162323030313030')
    
    headers = {
        "accept": "text/event-stream",
        "content-type": "application/x-protobuf",
        "x-warp-client-version": "v0.2025.08.06.08.12.stable_02",
        "x-warp-os-category": "Windows",
        "x-warp-os-name": "Windows",
        "x-warp-os-version": "11 (26100)",
        "authorization": f"Bearer {access_token}",
        "content-length": str(len(test_data)),
    }
    
    async with httpx.AsyncClient(timeout=30.0, http2=True) as client:
        response = await client.post(url, headers=headers, content=test_data)
        
        print(f"   状态码: {response.status_code}")
        
        if response.status_code == 200:
            print(f"   ✅ 个人Token工作正常")
            return "working"
            
        elif response.status_code == 429:
            try:
                error_data = response.json()
                print(f"   ❌ 429错误: {error_data}")
                print(f"\n   ⚠️ 结论: 个人Token配额已用尽")
                return "quota_exhausted"
            except:
                print(f"   ❌ 429错误")
                return "quota_exhausted"
                
        elif response.status_code == 500:
            print(f"   ❌ 500错误: 服务器内部错误")
            print(f"   Content-Length: {response.headers.get('content-length', 'N/A')}")
            print(f"\n   ⚠️ 结论: Warp服务器返回500错误")
            return "server_error_500"
            
        elif response.status_code == 401:
            print(f"   ❌ 401错误: 未授权")
            print(f"\n   ⚠️ 结论: Token认证失败")
            return "unauthorized"
            
        else:
            print(f"   ❌ {response.status_code}错误: {response.text[:100]}")
            return f"error_{response.status_code}"


async def main():
    """运行所有测试"""
    print("🚀 Warp API限制综合分析")
    print("=" * 80)
    print("测试目标: 确定Warp API是否有接口限制")
    print("=" * 80)
    
    results = {}
    
    # 测试1: 匿名Token创建限制
    results["anonymous_creation"] = await test_anonymous_token_creation()
    
    # 测试2: 匿名Token配额
    results["anonymous_quota"] = await test_anonymous_token_quota()
    
    # 测试3: 个人Token状态
    results["personal_status"] = await test_personal_token_status()
    
    # 综合分析
    print("\n" + "=" * 80)
    print("📊 综合分析结果")
    print("=" * 80)
    
    print("\n1️⃣ 匿名Token创建限制:")
    creation_results = results["anonymous_creation"]
    if creation_results:
        rate_limit_count = sum(1 for r in creation_results if r[0] == "rate_limit")
        if rate_limit_count > 0:
            print("   ⚠️ 存在速率限制 - 短时间内不能频繁创建匿名用户")
        else:
            print("   ✅ 可以正常创建匿名用户")
    
    print("\n2️⃣ 匿名Token配额:")
    if results["anonymous_quota"] == "has_quota":
        print("   ✅ 匿名Token仍有配额可用")
    elif results["anonymous_quota"] == "quota_exhausted":
        print("   ⚠️ 匿名Token配额已用尽")
    elif results["anonymous_quota"] == "server_error":
        print("   ❌ 匿名Token也遇到500错误")
    
    print("\n3️⃣ 个人Token状态:")
    if results["personal_status"] == "working":
        print("   ✅ 个人Token工作正常")
    elif results["personal_status"] == "quota_exhausted":
        print("   ⚠️ 个人Token配额已用尽")
    elif results["personal_status"] == "server_error_500":
        print("   ❌ 个人Token遇到500错误")
    elif results["personal_status"] == "invalid_token":
        print("   ❌ 个人Token无效或已过期")
    elif results["personal_status"] == "unauthorized":
        print("   ❌ 个人Token认证失败")
    
    # 最终结论
    print("\n" + "=" * 80)
    print("🎯 最终结论")
    print("=" * 80)
    
    if results["personal_status"] == "server_error_500":
        print("\n⚠️ Warp API接口限制分析:")
        print("   1. 个人Token认证成功（Token刷新返回200）")
        print("   2. 但是AI请求返回500错误（服务器内部错误）")
        print("   3. 所有不同的请求数据都返回500")
        print("   4. 请求头完整且正确")
        print("\n   可能的原因:")
        print("   ❌ 个人Token账户被Warp限制或封禁")
        print("   ❌ Warp对个人Token有特殊的使用限制")
        print("   ❌ Warp服务器对该账户返回500错误")
        print("\n   建议:")
        print("   1. 检查Warp账户状态")
        print("   2. 尝试在Warp官方客户端登录")
        print("   3. 联系Warp支持询问账户状态")
        print("   4. 暂时使用匿名Token（配额有限但可用）")
    
    elif results["anonymous_quota"] == "quota_exhausted" and results["personal_status"] == "quota_exhausted":
        print("\n⚠️ 所有Token配额都已用尽:")
        print("   1. 匿名Token配额用尽")
        print("   2. 个人Token配额用尽")
        print("   3. 需要等待配额重置")
    
    elif results["anonymous_quota"] == "has_quota" and results["personal_status"] == "working":
        print("\n✅ Warp API工作正常:")
        print("   1. 匿名Token可用")
        print("   2. 个人Token可用")
        print("   3. 没有接口限制")


if __name__ == "__main__":
    asyncio.run(main())

