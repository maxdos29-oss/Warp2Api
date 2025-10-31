#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test the actual request that's failing"""

import asyncio
import json
from warp2protobuf.core.protobuf_utils import dict_to_protobuf_bytes
from warp2protobuf.warp.api_client import send_protobuf_to_warp_api_parsed

async def test_actual_request():
    """Test with the actual request data from the logs"""
    
    # This is the exact data from your logs
    request_data = {
        "task_context": {
            "active_task_id": "7565cdc1-972e-470b-bcd4-7beec7ed9eaf"
        },
        "input": {
            "context": {},
            "user_inputs": {
                "inputs": [
                    {
                        "user_query": {
                            "query": "warmup"
                        }
                    }
                ]
            }
        },
        "settings": {
            "model_config": {
                "base": "claude-4.1-opus",
                "planning": "gpt-5 (high reasoning)",
                "coding": "auto"
            },
            "rules_enabled": False,
            "web_context_retrieval_enabled": False,
            "supports_parallel_tool_calls": False,
            "planning_enabled": False,
            "warp_drive_context_enabled": False,
            "supports_create_files": False,
            "use_anthropic_text_editor_tools": False,
            "supports_long_running_commands": False,
            "should_preserve_file_content_in_history": False,
            "supports_todos_ui": False,
            "supports_linked_code_blocks": False,
            "supported_tools": [9]
        },
        "metadata": {
            "logging": {
                "is_autodetected_user_query": True,
                "entrypoint": "USER_INITIATED"
            }
        }
    }
    
    print("="*60)
    print("Testing actual request from logs")
    print("="*60)
    
    print("\n📋 Request Data:")
    print(json.dumps(request_data, indent=2))
    
    print("\n🔄 Encoding to protobuf...")
    try:
        protobuf_bytes = dict_to_protobuf_bytes(request_data, "warp.multi_agent.v1.Request")
        print(f"✅ Protobuf encoding successful")
        print(f"   Size: {len(protobuf_bytes)} bytes")
        print(f"   Hex (first 64 bytes): {protobuf_bytes[:64].hex()}")
    except Exception as e:
        print(f"❌ Protobuf encoding failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n📤 Sending to Warp API...")
    try:
        response_text, conversation_id, task_id, parsed_events = await send_protobuf_to_warp_api_parsed(protobuf_bytes)
        
        print(f"\n✅ Request completed")
        print(f"   Response length: {len(response_text)} characters")
        print(f"   Conversation ID: {conversation_id}")
        print(f"   Task ID: {task_id}")
        print(f"   Events count: {len(parsed_events)}")
        
        if response_text:
            print(f"\n📥 Response preview:")
            print(f"   {response_text[:200]}")
        
        if parsed_events:
            print(f"\n📊 Events:")
            for i, event in enumerate(parsed_events[:5]):
                print(f"   Event {i+1}: {event.get('type', 'unknown')}")
    
    except Exception as e:
        print(f"\n❌ Request failed: {e}")
        import traceback
        traceback.print_exc()


async def test_minimal_request():
    """Test with a minimal request"""
    
    print("\n" + "="*60)
    print("Testing minimal request")
    print("="*60)
    
    # Minimal request with only required fields
    minimal_data = {
        "input": {
            "user_inputs": {
                "inputs": [
                    {
                        "user_query": {
                            "query": "Hello"
                        }
                    }
                ]
            }
        }
    }
    
    print("\n📋 Minimal Request Data:")
    print(json.dumps(minimal_data, indent=2))
    
    print("\n🔄 Encoding to protobuf...")
    try:
        protobuf_bytes = dict_to_protobuf_bytes(minimal_data, "warp.multi_agent.v1.Request")
        print(f"✅ Protobuf encoding successful")
        print(f"   Size: {len(protobuf_bytes)} bytes")
    except Exception as e:
        print(f"❌ Protobuf encoding failed: {e}")
        return
    
    print("\n📤 Sending to Warp API...")
    try:
        response_text, conversation_id, task_id, parsed_events = await send_protobuf_to_warp_api_parsed(protobuf_bytes)
        
        print(f"\n✅ Request completed")
        print(f"   Response length: {len(response_text)} characters")
        print(f"   Events count: {len(parsed_events)}")
    
    except Exception as e:
        print(f"\n❌ Request failed: {e}")


async def main():
    print("🔍 Testing Warp API Requests")
    print("="*60)
    
    # Test 1: Actual request from logs
    await test_actual_request()
    
    # Test 2: Minimal request
    await test_minimal_request()
    
    print("\n" + "="*60)
    print("Testing complete")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())

