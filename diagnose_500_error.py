#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Diagnose 500 error from Warp API"""

import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

async def test_warp_api():
    """Test Warp API with minimal request"""
    
    # Get JWT token
    jwt = os.getenv('WARP_JWT', '')
    if not jwt:
        print("❌ No JWT token found")
        return
    
    print(f"✅ JWT token found (length: {len(jwt)})")
    
    # Create a minimal test request
    # This is a simple protobuf message for testing
    test_protobuf = bytes.fromhex("0a26122435366430363265322d626537332d346631342d616363652d30303038")
    
    print(f"\n📤 Sending test request to Warp API...")
    print(f"   Protobuf size: {len(test_protobuf)} bytes")
    print(f"   Hex preview: {test_protobuf[:32].hex()}")
    
    warp_url = "https://app.warp.dev/ai/multi-agent"
    
    headers = {
        "accept": "text/event-stream",
        "content-type": "application/x-protobuf",
        "x-warp-client-version": "v0.2025.08.06.08.12.stable_02",
        "x-warp-os-category": "Windows",
        "x-warp-os-name": "Windows",
        "x-warp-os-version": "11 (26100)",
        "authorization": f"Bearer {jwt}",
        "content-length": str(len(test_protobuf)),
    }
    
    try:
        async with httpx.AsyncClient(http2=True, timeout=httpx.Timeout(30.0)) as client:
            print(f"\n🔗 Connecting to: {warp_url}")
            
            async with client.stream("POST", warp_url, headers=headers, content=test_protobuf) as response:
                print(f"\n📥 Response received:")
                print(f"   Status code: {response.status_code}")
                print(f"   Headers: {dict(response.headers)}")
                
                if response.status_code != 200:
                    error_text = await response.aread()
                    error_content = error_text.decode('utf-8') if error_text else "No error content"
                    print(f"\n❌ Error response:")
                    print(f"   Status: {response.status_code}")
                    print(f"   Content: {error_content[:500]}")
                    
                    # Analyze error
                    if response.status_code == 500:
                        print(f"\n🔍 500 Error Analysis:")
                        print(f"   - This is a server-side error from Warp API")
                        print(f"   - Possible causes:")
                        print(f"     1. Invalid protobuf format")
                        print(f"     2. Token is valid but has insufficient permissions")
                        print(f"     3. Warp API server internal error")
                        print(f"     4. Request data is malformed")
                        
                        if not error_content or error_content == "No error content":
                            print(f"\n   ⚠️  Server returned no error details")
                            print(f"   This usually means:")
                            print(f"     - The server crashed before generating an error message")
                            print(f"     - The protobuf data is completely invalid")
                            print(f"     - There's a bug in Warp API server")
                    
                    elif response.status_code == 429:
                        print(f"\n🔍 429 Error Analysis:")
                        print(f"   - Token quota exhausted")
                        print(f"   - Need to switch to another token or wait for quota reset")
                    
                    elif response.status_code == 401:
                        print(f"\n🔍 401 Error Analysis:")
                        print(f"   - JWT token is invalid or expired")
                        print(f"   - Need to refresh the token")
                    
                    return False
                
                else:
                    print(f"\n✅ Request successful!")
                    print(f"   Reading response stream...")
                    
                    event_count = 0
                    async for line in response.aiter_lines():
                        if line.strip():
                            event_count += 1
                            if event_count <= 5:
                                print(f"   Event {event_count}: {line[:100]}")
                    
                    print(f"\n✅ Received {event_count} events")
                    return True
    
    except httpx.TimeoutException:
        print(f"\n❌ Request timed out")
        print(f"   - The server took too long to respond")
        print(f"   - This might indicate server overload")
        return False
    
    except httpx.ConnectError as e:
        print(f"\n❌ Connection error: {e}")
        print(f"   - Cannot connect to Warp API")
        print(f"   - Check your internet connection")
        return False
    
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_token_refresh():
    """Test token refresh functionality"""
    print(f"\n" + "="*60)
    print(f"🔄 Testing Token Refresh...")
    print(f"="*60)
    
    try:
        from warp2protobuf.core.auth import refresh_jwt_token
        
        print(f"\n📤 Attempting to refresh JWT token...")
        token_data = await refresh_jwt_token()
        
        if token_data and "access_token" in token_data:
            jwt = token_data["access_token"]
            print(f"✅ Token refresh successful!")
            print(f"   New JWT length: {len(jwt)} characters")
            print(f"   JWT preview: {jwt[:50]}...")
            return True
        else:
            print(f"❌ Token refresh failed")
            return False
    
    except Exception as e:
        print(f"❌ Error during token refresh: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    print("="*60)
    print("🔍 Warp API 500 Error Diagnostic Tool")
    print("="*60)
    
    # Test 1: Check current JWT and make a request
    print(f"\n📋 Test 1: Testing with current JWT token")
    success = await test_warp_api()
    
    if not success:
        # Test 2: Try refreshing token
        print(f"\n📋 Test 2: Attempting token refresh")
        refresh_success = await test_token_refresh()
        
        if refresh_success:
            # Test 3: Retry with new token
            print(f"\n📋 Test 3: Retrying with refreshed token")
            success = await test_warp_api()
    
    print(f"\n" + "="*60)
    if success:
        print(f"✅ Diagnostic complete: API is working")
    else:
        print(f"❌ Diagnostic complete: API requests are failing")
        print(f"\n💡 Recommendations:")
        print(f"   1. Check if you have multiple tokens configured")
        print(f"   2. Try adding more tokens to .env file:")
        print(f"      WARP_PERSONAL_TOKENS='token2,token3'")
        print(f"   3. Wait for quota to reset (usually daily)")
        print(f"   4. Check Warp API status: https://status.warp.dev")
    print(f"="*60)


if __name__ == "__main__":
    asyncio.run(main())

