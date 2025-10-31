#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Warp API客户端模块

处理与Warp API的通信，包括protobuf数据发送和SSE响应解析。
"""
import httpx
import os
import base64
import binascii
import time
from typing import Optional, Any, Dict
from urllib.parse import urlparse
import socket

from ..core.logging import logger
from ..core.protobuf_utils import protobuf_to_dict
from ..core.auth import get_valid_jwt, acquire_anonymous_access_token
from ..core.token_pool import get_token_pool
from ..config.settings import WARP_URL as CONFIG_WARP_URL


def _get(d: Dict[str, Any], *names: str) -> Any:
    """Return the first matching key value (camelCase/snake_case tolerant)."""
    for name in names:
        if name in d:
            return d[name]
    return None


def _get_event_type(event_data: dict) -> str:
    """Determine the type of SSE event for logging"""
    if "init" in event_data:
        return "INITIALIZATION"
    client_actions = _get(event_data, "client_actions", "clientActions")
    if isinstance(client_actions, dict):
        actions = _get(client_actions, "actions", "Actions") or []
        if not actions:
            return "CLIENT_ACTIONS_EMPTY"
        
        action_types = []
        for action in actions:
            if _get(action, "create_task", "createTask") is not None:
                action_types.append("CREATE_TASK")
            elif _get(action, "append_to_message_content", "appendToMessageContent") is not None:
                action_types.append("APPEND_CONTENT")
            elif _get(action, "add_messages_to_task", "addMessagesToTask") is not None:
                action_types.append("ADD_MESSAGE")
            elif _get(action, "tool_call", "toolCall") is not None:
                action_types.append("TOOL_CALL")
            elif _get(action, "tool_response", "toolResponse") is not None:
                action_types.append("TOOL_RESPONSE")
            else:
                action_types.append("UNKNOWN_ACTION")
        
        return f"CLIENT_ACTIONS({', '.join(action_types)})"
    elif "finished" in event_data:
        return "FINISHED"
    else:
        return "UNKNOWN_EVENT"


async def send_protobuf_to_warp_api(
    protobuf_bytes: bytes, show_all_events: bool = True
) -> tuple[str, Optional[str], Optional[str]]:
    """发送protobuf数据到Warp API并获取响应"""
    try:
        logger.info(f"发送 {len(protobuf_bytes)} 字节到Warp API")
        logger.info(f"数据包前32字节 (hex): {protobuf_bytes[:32].hex()}")
        
        warp_url = CONFIG_WARP_URL
        
        logger.info(f"发送请求到: {warp_url}")
        
        conversation_id = None
        task_id = None
        complete_response = []
        all_events = []
        event_count = 0
        
        verify_opt = True
        insecure_env = os.getenv("WARP_INSECURE_TLS", "").lower()
        if insecure_env in ("1", "true", "yes"):
            verify_opt = False
            logger.warning("TLS verification disabled via WARP_INSECURE_TLS for Warp API client")

        async with httpx.AsyncClient(http2=True, timeout=httpx.Timeout(60.0), verify=verify_opt, trust_env=True) as client:
            # 最多尝试两次：第一次失败且为配额429时申请匿名token并重试一次
            current_token_refresh = None  # Track which refresh token is being used
            current_token_info = None  # Track current TokenInfo object

            # 第一次请求：从token pool获取token
            if True:  # Always use token pool
                pool = await get_token_pool()
                current_token_info = await pool.get_next_token()
                if current_token_info:
                    # 检查JWT是否有效，如果无效则刷新
                    if current_token_info.last_jwt and current_token_info.last_jwt_expiry > time.time() + 120:
                        # JWT有效且未过期（至少还有2分钟）
                        jwt = current_token_info.last_jwt
                        logger.info(f"🎯 使用token pool中的token: {current_token_info.name} (优先级: {current_token_info.priority.name}, 使用缓存JWT)")
                    else:
                        # JWT无效或即将过期，需要刷新
                        logger.info(f"🔄 刷新token pool中的token: {current_token_info.name}")
                        from ..core.auth import refresh_jwt_token_with_token_info
                        token_data = await refresh_jwt_token_with_token_info(current_token_info)
                        if token_data and "access_token" in token_data:
                            jwt = token_data["access_token"]
                            logger.info(f"✅ Token刷新成功: {current_token_info.name}")
                        else:
                            logger.error(f"❌ Token刷新失败，使用环境变量中的JWT")
                            jwt = await get_valid_jwt()

                    current_token_refresh = current_token_info.refresh_token
                else:
                    # Fallback to old method if pool is empty
                    jwt = await get_valid_jwt()
                    logger.warning("⚠️ Token pool为空，使用环境变量中的JWT")

            for attempt in range(2):
                headers = {
                    "accept": "text/event-stream",
                    "content-type": "application/x-protobuf", 
                    "x-warp-client-version": "v0.2025.08.06.08.12.stable_02",
                    "x-warp-os-category": "Windows",
                    "x-warp-os-name": "Windows", 
                    "x-warp-os-version": "11 (26100)",
                    "authorization": f"Bearer {jwt}",
                    "content-length": str(len(protobuf_bytes)),
                }
                async with client.stream("POST", warp_url, headers=headers, content=protobuf_bytes) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        error_content = error_text.decode('utf-8') if error_text else "No error content"

                        # 记录详细的错误信息
                        logger.error(f"❌ Warp API返回错误状态码: {response.status_code}")
                        logger.error(f"   错误内容: {error_content[:500]}")
                        logger.error(f"   响应头: {dict(response.headers)}")
                        logger.error(f"   请求大小: {len(protobuf_bytes)} 字节")
                        logger.error(f"   尝试次数: {attempt + 1}/2")

                        # 检测配额耗尽错误并在第一次失败时尝试使用token pool中的下一个token
                        if response.status_code == 429 and attempt == 0 and (
                            ("No remaining quota" in error_content) or ("No AI requests remaining" in error_content)
                        ):
                            logger.warning("⚠️ WARP API 返回 429 (配额用尽)。尝试从token pool获取下一个token并重试…")
                            try:
                                # 尝试从token pool获取下一个可用token（排除当前失败的token）
                                pool = await get_token_pool()

                                # 显示当前token pool状态
                                pool_stats = await pool.get_pool_stats()
                                logger.info(f"📊 Token pool状态: 总数={pool_stats['total_tokens']}, 活跃={pool_stats['active_tokens']}, 匿名={pool_stats['anonymous_tokens']}, 个人={pool_stats['personal_tokens']}")

                                # 如果current_token_refresh为None，尝试获取最后使用的token
                                if current_token_refresh is None:
                                    last_used = pool.get_last_used_token()
                                    if last_used:
                                        current_token_refresh = last_used.refresh_token
                                        logger.info(f"🔍 检测到最后使用的token: {last_used.name} (last_used={last_used.last_used})")
                                    else:
                                        logger.warning("⚠️ 无法检测到最后使用的token")
                                else:
                                    logger.info(f"🔍 当前使用的token: {current_token_refresh[:20]}...")

                                logger.info(f"🔄 尝试获取下一个token (排除: {current_token_refresh[:20] if current_token_refresh else 'None'}...)")
                                token_info = await pool.get_next_token_excluding(current_token_refresh)
                                logger.info(f"🔍 get_next_token_excluding返回: {token_info.name if token_info else 'None'}")

                                if not token_info:
                                    # 没有其他token了，尝试申请新的匿名token
                                    logger.warning("⚠️ Token pool中没有其他可用token，尝试申请新的匿名token…")
                                    try:
                                        new_jwt = await acquire_anonymous_access_token()
                                        if new_jwt:
                                            logger.info("✅ 成功申请新的匿名token")
                                            jwt = new_jwt
                                            current_token_refresh = None  # New anonymous token
                                            continue
                                    except Exception as anon_err:
                                        logger.error(f"❌ 申请匿名token失败: {anon_err}")

                                    logger.error("❌ 所有token尝试失败")
                                    logger.error(f"WARP API HTTP ERROR {response.status_code}: {error_content}")
                                    return f"❌ Warp API Error (HTTP {response.status_code}): {error_content}", None, None

                                if token_info and token_info.last_jwt:
                                    # 使用缓存的JWT
                                    logger.info(f"✅ 使用token pool中的下一个token: {token_info.name}")
                                    jwt = token_info.last_jwt
                                    current_token_refresh = token_info.refresh_token  # Track current token
                                    continue
                                elif token_info:
                                    # 需要刷新JWT
                                    logger.info(f"🔄 刷新token pool中的token: {token_info.name}")
                                    from ..core.auth import refresh_jwt_token_with_token_info
                                    token_data = await refresh_jwt_token_with_token_info(token_info)
                                    if token_data and "access_token" in token_data:
                                        jwt = token_data["access_token"]
                                        current_token_refresh = token_info.refresh_token  # Track current token
                                        logger.info(f"✅ Token刷新成功，使用新JWT重试")
                                        continue

                            except Exception as e:
                                logger.error(f"❌ Token pool处理失败: {e}")

                            # 如果到这里，说明所有尝试都失败了
                            logger.error(f"WARP API HTTP ERROR {response.status_code}: {error_content}")
                            return f"❌ Warp API Error (HTTP {response.status_code}): {error_content}", None, None

                        # 特殊处理500错误 - 可能是token问题，尝试切换token
                        if response.status_code == 500 and attempt == 0:
                            logger.warning("⚠️ WARP API 返回 500 (服务器错误)。尝试切换到下一个token重试…")
                            try:
                                pool = await get_token_pool()

                                # 如果current_token_refresh为None，尝试获取最后使用的token
                                if current_token_refresh is None:
                                    last_used = pool.get_last_used_token()
                                    if last_used:
                                        current_token_refresh = last_used.refresh_token
                                        logger.info(f"🔍 检测到最后使用的token: {last_used.name}")

                                # 获取下一个token（排除当前失败的token）
                                token_info = await pool.get_next_token_excluding(current_token_refresh)

                                if token_info:
                                    logger.info(f"🔄 切换到token: {token_info.name}")
                                    current_token_refresh = token_info.refresh_token  # 更新当前token
                                    from ..core.auth import refresh_jwt_token_with_token_info
                                    token_data = await refresh_jwt_token_with_token_info(token_info)
                                    if token_data and "access_token" in token_data:
                                        jwt = token_data["access_token"]
                                        logger.info(f"✅ 使用新token重试")
                                        continue
                            except Exception as e:
                                logger.error(f"❌ 切换token失败: {e}")

                        # 其他错误或第二次失败
                        logger.error(f"WARP API HTTP ERROR {response.status_code}: {error_content}")
                        return f"❌ Warp API Error (HTTP {response.status_code}): {error_content}", None, None
                    
                    logger.info(f"✅ 收到HTTP {response.status_code}响应")
                    logger.info("开始处理SSE事件流...")
                    
                    import re as _re
                    def _parse_payload_bytes(data_str: str):
                        s = _re.sub(r"\s+", "", data_str or "")
                        if not s:
                            return None
                        if _re.fullmatch(r"[0-9a-fA-F]+", s or ""):
                            try:
                                return bytes.fromhex(s)
                            except Exception:
                                pass
                        pad = "=" * ((4 - (len(s) % 4)) % 4)
                        try:
                            import base64 as _b64
                            return _b64.urlsafe_b64decode(s + pad)
                        except Exception:
                            try:
                                return _b64.b64decode(s + pad)
                            except Exception:
                                return None
                    
                    current_data = ""
                    
                    async for line in response.aiter_lines():
                        if line.startswith("data:"):
                            payload = line[5:].strip()
                            if not payload:
                                continue
                            if payload == "[DONE]":
                                logger.info("收到[DONE]标记，结束处理")
                                break
                            current_data += payload
                            continue
                        
                        if (line.strip() == "") and current_data:
                            raw_bytes = _parse_payload_bytes(current_data)
                            current_data = ""
                            if raw_bytes is None:
                                logger.debug("跳过无法解析的SSE数据块（非hex/base64或不完整）")
                                continue
                            try:
                                event_data = protobuf_to_dict(raw_bytes, "warp.multi_agent.v1.ResponseEvent")
                            except Exception as parse_error:
                                logger.debug(f"解析事件失败，跳过: {str(parse_error)[:100]}")
                                continue
                            event_count += 1
                            
                            def _get(d: Dict[str, Any], *names: str) -> Any:
                                for n in names:
                                    if isinstance(d, dict) and n in d:
                                        return d[n]
                                return None
                            
                            event_type = _get_event_type(event_data)
                            if show_all_events:
                                all_events.append({"event_number": event_count, "event_type": event_type, "raw_data": event_data})
                            logger.info(f"🔄 Event #{event_count}: {event_type}")
                            if show_all_events:
                                logger.info(f"   📋 Event data: {str(event_data)}...")
                            
                            if "init" in event_data:
                                init_data = event_data["init"]
                                conversation_id = init_data.get("conversation_id", conversation_id)
                                task_id = init_data.get("task_id", task_id)
                                logger.info(f"会话初始化: {conversation_id}")
                                client_actions = _get(event_data, "client_actions", "clientActions")
                                if isinstance(client_actions, dict):
                                    actions = _get(client_actions, "actions", "Actions") or []
                                    for i, action in enumerate(actions):
                                        logger.info(f"   🎯 Action #{i+1}: {list(action.keys())}")
                                        append_data = _get(action, "append_to_message_content", "appendToMessageContent")
                                        if isinstance(append_data, dict):
                                            message = append_data.get("message", {})
                                            agent_output = _get(message, "agent_output", "agentOutput") or {}
                                            text_content = agent_output.get("text", "")
                                            if text_content:
                                                complete_response.append(text_content)
                                                logger.info(f"   📝 Text Fragment: {text_content[:100]}...")
                                        messages_data = _get(action, "add_messages_to_task", "addMessagesToTask")
                                        if isinstance(messages_data, dict):
                                            messages = messages_data.get("messages", [])
                                            task_id = messages_data.get("task_id", messages_data.get("taskId", task_id))
                                            for j, message in enumerate(messages):
                                                logger.info(f"   📨 Message #{j+1}: {list(message.keys())}")
                                                if _get(message, "agent_output", "agentOutput") is not None:
                                                    agent_output = _get(message, "agent_output", "agentOutput") or {}
                                                    text_content = agent_output.get("text", "")
                                                    if text_content:
                                                        complete_response.append(text_content)
                                                        logger.info(f"   📝 Complete Message: {text_content[:100]}...")
                    
                    full_response = "".join(complete_response)
                    logger.info("="*60)
                    logger.info("📊 SSE STREAM SUMMARY")
                    logger.info("="*60)
                    logger.info(f"📈 Total Events Processed: {event_count}")
                    logger.info(f"🆔 Conversation ID: {conversation_id}")
                    logger.info(f"🆔 Task ID: {task_id}")
                    logger.info(f"📝 Response Length: {len(full_response)} characters")
                    logger.info("="*60)
                    if full_response:
                        logger.info(f"✅ Stream processing completed successfully")
                        return full_response, conversation_id, task_id
                    else:
                        logger.warning("⚠️ No text content received in response")
                        return "Warning: No response content received", conversation_id, task_id
    except Exception as e:
        import traceback
        logger.error("="*60)
        logger.error("WARP API CLIENT EXCEPTION")
        logger.error("="*60)
        logger.error(f"Exception Type: {type(e).__name__}")
        logger.error(f"Exception Message: {str(e)}")
        logger.error(f"Request URL: {warp_url if 'warp_url' in locals() else 'Unknown'}")
        logger.error(f"Request Size: {len(protobuf_bytes) if 'protobuf_bytes' in locals() else 'Unknown'}")
        logger.error("Python Traceback:")
        logger.error(traceback.format_exc())
        logger.error("="*60)
        raise


async def send_protobuf_to_warp_api_parsed(protobuf_bytes: bytes) -> tuple[str, Optional[str], Optional[str], list]:
    """发送protobuf数据到Warp API并获取解析后的SSE事件数据"""
    try:
        logger.info(f"发送 {len(protobuf_bytes)} 字节到Warp API (解析模式)")
        logger.info(f"数据包前32字节 (hex): {protobuf_bytes[:32].hex()}")
        
        warp_url = CONFIG_WARP_URL
        
        logger.info(f"发送请求到: {warp_url}")
        
        conversation_id = None
        task_id = None
        complete_response = []
        parsed_events = []
        event_count = 0
        
        verify_opt = True
        insecure_env = os.getenv("WARP_INSECURE_TLS", "").lower()
        if insecure_env in ("1", "true", "yes"):
            verify_opt = False
            logger.warning("TLS verification disabled via WARP_INSECURE_TLS for Warp API client")

        async with httpx.AsyncClient(http2=True, timeout=httpx.Timeout(60.0), verify=verify_opt, trust_env=True) as client:
            # 最多尝试两次：第一次失败且为配额429时申请匿名token并重试一次
            current_token_refresh = None  # Track which refresh token is being used
            current_token_info = None  # Track current TokenInfo object

            # 第一次请求：从token pool获取token
            if True:  # Always use token pool
                pool = await get_token_pool()
                current_token_info = await pool.get_next_token()
                if current_token_info:
                    # 检查JWT是否有效，如果无效则刷新
                    if current_token_info.last_jwt and current_token_info.last_jwt_expiry > time.time() + 120:
                        # JWT有效且未过期（至少还有2分钟）
                        jwt = current_token_info.last_jwt
                        logger.info(f"🎯 使用token pool中的token (解析模式): {current_token_info.name} (优先级: {current_token_info.priority.name}, 使用缓存JWT)")
                    else:
                        # JWT无效或即将过期，需要刷新
                        logger.info(f"🔄 刷新token pool中的token (解析模式): {current_token_info.name}")
                        from ..core.auth import refresh_jwt_token_with_token_info
                        token_data = await refresh_jwt_token_with_token_info(current_token_info)
                        if token_data and "access_token" in token_data:
                            jwt = token_data["access_token"]
                            logger.info(f"✅ Token刷新成功 (解析模式): {current_token_info.name}")
                        else:
                            logger.error(f"❌ Token刷新失败，使用环境变量中的JWT (解析模式)")
                            jwt = await get_valid_jwt()

                    current_token_refresh = current_token_info.refresh_token
                else:
                    # Fallback to old method if pool is empty
                    jwt = await get_valid_jwt()
                    logger.warning("⚠️ Token pool为空，使用环境变量中的JWT (解析模式)")

            for attempt in range(2):
                headers = {
                    "accept": "text/event-stream",
                    "content-type": "application/x-protobuf", 
                    "x-warp-client-version": "v0.2025.08.06.08.12.stable_02",
                    "x-warp-os-category": "Windows",
                    "x-warp-os-name": "Windows", 
                    "x-warp-os-version": "11 (26100)",
                    "authorization": f"Bearer {jwt}",
                    "content-length": str(len(protobuf_bytes)),
                }
                async with client.stream("POST", warp_url, headers=headers, content=protobuf_bytes) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        error_content = error_text.decode('utf-8') if error_text else "No error content"

                        # 记录详细的错误信息
                        logger.error(f"❌ Warp API返回错误状态码: {response.status_code}")
                        logger.error(f"   错误内容: {error_content[:500]}")
                        logger.error(f"   响应头: {dict(response.headers)}")
                        logger.error(f"   请求大小: {len(protobuf_bytes)} 字节")
                        logger.error(f"   尝试次数: {attempt + 1}/2")

                        # 检测配额耗尽错误并在第一次失败时尝试使用token pool中的下一个token
                        if response.status_code == 429 and attempt == 0 and (
                            ("No remaining quota" in error_content) or ("No AI requests remaining" in error_content)
                        ):
                            logger.warning("⚠️ WARP API 返回 429 (配额用尽, 解析模式)。尝试从token pool获取下一个token并重试…")
                            try:
                                # 尝试从token pool获取下一个可用token（排除当前失败的token）
                                pool = await get_token_pool()

                                # 显示当前token pool状态
                                pool_stats = await pool.get_pool_stats()
                                logger.info(f"📊 Token pool状态 (解析模式): 总数={pool_stats['total_tokens']}, 活跃={pool_stats['active_tokens']}, 匿名={pool_stats['anonymous_tokens']}, 个人={pool_stats['personal_tokens']}")

                                # 如果current_token_refresh为None，尝试获取最后使用的token
                                if current_token_refresh is None:
                                    last_used = pool.get_last_used_token()
                                    if last_used:
                                        current_token_refresh = last_used.refresh_token
                                        logger.info(f"🔍 检测到最后使用的token (解析模式): {last_used.name} (last_used={last_used.last_used})")
                                    else:
                                        logger.warning("⚠️ 无法检测到最后使用的token (解析模式)")
                                else:
                                    logger.info(f"🔍 当前使用的token (解析模式): {current_token_refresh[:20]}...")

                                logger.info(f"🔄 尝试获取下一个token (解析模式, 排除: {current_token_refresh[:20] if current_token_refresh else 'None'}...)")
                                token_info = await pool.get_next_token_excluding(current_token_refresh)
                                logger.info(f"🔍 get_next_token_excluding返回 (解析模式): {token_info.name if token_info else 'None'}")

                                if not token_info:
                                    # 没有其他token了，尝试申请新的匿名token
                                    logger.warning("⚠️ Token pool中没有其他可用token，尝试申请新的匿名token…")
                                    try:
                                        new_jwt = await acquire_anonymous_access_token()
                                        if new_jwt:
                                            logger.info("✅ 成功申请新的匿名token (解析模式)")
                                            jwt = new_jwt
                                            current_token_refresh = None  # New anonymous token
                                            continue
                                    except Exception as anon_err:
                                        logger.error(f"❌ 申请匿名token失败: {anon_err}")

                                    logger.error("❌ 所有token尝试失败")
                                    logger.error(f"WARP API HTTP ERROR (解析模式) {response.status_code}: {error_content}")
                                    return f"❌ Warp API Error (HTTP {response.status_code}): {error_content}", None, None, []

                                if token_info and token_info.last_jwt:
                                    # 使用缓存的JWT
                                    logger.info(f"✅ 使用token pool中的下一个token: {token_info.name} (解析模式)")
                                    jwt = token_info.last_jwt
                                    current_token_refresh = token_info.refresh_token  # Track current token
                                    continue
                                elif token_info:
                                    # 需要刷新JWT
                                    logger.info(f"🔄 刷新token pool中的token: {token_info.name} (解析模式)")
                                    from ..core.auth import refresh_jwt_token_with_token_info
                                    token_data = await refresh_jwt_token_with_token_info(token_info)
                                    if token_data and "access_token" in token_data:
                                        jwt = token_data["access_token"]
                                        current_token_refresh = token_info.refresh_token  # Track current token
                                        logger.info(f"✅ Token刷新成功，使用新JWT重试 (解析模式)")
                                        continue

                                # 如果token pool中没有可用token，尝试申请匿名token作为最后手段
                                logger.warning("⚠️ Token pool中没有可用token，尝试申请匿名token作为后备… (解析模式)")
                                new_jwt = await acquire_anonymous_access_token()
                                if new_jwt:
                                    jwt = new_jwt
                                    continue

                            except Exception as e:
                                logger.error(f"❌ Token pool处理失败 (解析模式): {e}")

                            # 如果到这里，说明所有尝试都失败了
                            logger.error(f"WARP API HTTP ERROR (解析模式) {response.status_code}: {error_content}")
                            return f"❌ Warp API Error (HTTP {response.status_code}): {error_content}", None, None, []

                        # 特殊处理500错误 - 可能是token问题，尝试切换token
                        if response.status_code == 500 and attempt == 0:
                            logger.warning("⚠️ WARP API 返回 500 (服务器错误)。尝试切换到下一个token重试…")
                            try:
                                pool = await get_token_pool()

                                # 如果current_token_refresh为None，尝试获取最后使用的token
                                if current_token_refresh is None:
                                    last_used = pool.get_last_used_token()
                                    if last_used:
                                        current_token_refresh = last_used.refresh_token
                                        logger.info(f"🔍 检测到最后使用的token: {last_used.name}")

                                # 获取下一个token（排除当前失败的token）
                                token_info = await pool.get_next_token_excluding(current_token_refresh)

                                if token_info:
                                    logger.info(f"🔄 切换到token: {token_info.name}")
                                    current_token_refresh = token_info.refresh_token  # 更新当前token
                                    from ..core.auth import refresh_jwt_token_with_token_info
                                    token_data = await refresh_jwt_token_with_token_info(token_info)
                                    if token_data and "access_token" in token_data:
                                        jwt = token_data["access_token"]
                                        logger.info(f"✅ 使用新token重试")
                                        continue
                            except Exception as e:
                                logger.error(f"❌ 切换token失败: {e}")

                        # 其他错误或第二次失败
                        logger.error(f"WARP API HTTP ERROR (解析模式) {response.status_code}: {error_content}")
                        return f"❌ Warp API Error (HTTP {response.status_code}): {error_content}", None, None, []
                    
                    logger.info(f"✅ 收到HTTP {response.status_code}响应 (解析模式)")
                    logger.info("开始处理SSE事件流...")
                    
                    import re as _re2
                    def _parse_payload_bytes2(data_str: str):
                        s = _re2.sub(r"\s+", "", data_str or "")
                        if not s:
                            return None
                        if _re2.fullmatch(r"[0-9a-fA-F]+", s or ""):
                            try:
                                return bytes.fromhex(s)
                            except Exception:
                                pass
                        pad = "=" * ((4 - (len(s) % 4)) % 4)
                        try:
                            import base64 as _b642
                            return _b642.urlsafe_b64decode(s + pad)
                        except Exception:
                            try:
                                return _b642.b64decode(s + pad)
                            except Exception:
                                return None
                    
                    current_data = ""
                    
                    async for line in response.aiter_lines():
                        if line.startswith("data:"):
                            payload = line[5:].strip()
                            if not payload:
                                continue
                            if payload == "[DONE]":
                                logger.info("收到[DONE]标记，结束处理")
                                break
                            current_data += payload
                            continue
                        
                        if (line.strip() == "") and current_data:
                            raw_bytes = _parse_payload_bytes2(current_data)
                            current_data = ""
                            if raw_bytes is None:
                                logger.debug("跳过无法解析的SSE数据块（非hex/base64或不完整）")
                                continue
                            try:
                                event_data = protobuf_to_dict(raw_bytes, "warp.multi_agent.v1.ResponseEvent")
                                event_count += 1
                                event_type = _get_event_type(event_data)
                                parsed_event = {"event_number": event_count, "event_type": event_type, "parsed_data": event_data}
                                parsed_events.append(parsed_event)
                                logger.info(f"🔄 Event #{event_count}: {event_type}")
                                logger.debug(f"   📋 Event data: {str(event_data)}...")
                                
                                def _get(d: Dict[str, Any], *names: str) -> Any:
                                    for n in names:
                                        if isinstance(d, dict) and n in d:
                                            return d[n]
                                    return None
                                
                                if "init" in event_data:
                                    init_data = event_data["init"]
                                    conversation_id = init_data.get("conversation_id", conversation_id)
                                    task_id = init_data.get("task_id", task_id)
                                    logger.info(f"会话初始化: {conversation_id}")
                                
                                client_actions = _get(event_data, "client_actions", "clientActions")
                                if isinstance(client_actions, dict):
                                    actions = _get(client_actions, "actions", "Actions") or []
                                    for i, action in enumerate(actions):
                                        logger.info(f"   🎯 Action #{i+1}: {list(action.keys())}")
                                        append_data = _get(action, "append_to_message_content", "appendToMessageContent")
                                        if isinstance(append_data, dict):
                                            message = append_data.get("message", {})
                                            agent_output = _get(message, "agent_output", "agentOutput") or {}
                                            text_content = agent_output.get("text", "")
                                            if text_content:
                                                complete_response.append(text_content)
                                                logger.info(f"   📝 Text Fragment: {text_content[:100]}...")
                                        messages_data = _get(action, "add_messages_to_task", "addMessagesToTask")
                                        if isinstance(messages_data, dict):
                                            messages = messages_data.get("messages", [])
                                            task_id = messages_data.get("task_id", messages_data.get("taskId", task_id))
                                            for j, message in enumerate(messages):
                                                logger.info(f"   📨 Message #{j+1}: {list(message.keys())}")
                                                if _get(message, "agent_output", "agentOutput") is not None:
                                                    agent_output = _get(message, "agent_output", "agentOutput") or {}
                                                    text_content = agent_output.get("text", "")
                                                    if text_content:
                                                        complete_response.append(text_content)
                                                        logger.info(f"   📝 Complete Message: {text_content[:100]}...")
                            except Exception as parse_err:
                                logger.debug(f"解析事件失败，跳过: {str(parse_err)[:100]}")
                                continue
                    
                    full_response = "".join(complete_response)
                    logger.info("="*60)
                    logger.info("📊 SSE STREAM SUMMARY (解析模式)")
                    logger.info("="*60)
                    logger.info(f"📈 Total Events Processed: {event_count}")
                    logger.info(f"🆔 Conversation ID: {conversation_id}")
                    logger.info(f"🆔 Task ID: {task_id}")
                    logger.info(f"📝 Response Length: {len(full_response)} characters")
                    logger.info(f"🎯 Parsed Events Count: {len(parsed_events)}")
                    logger.info("="*60)
                    
                    logger.info(f"✅ Stream processing completed successfully (解析模式)")
                    return full_response, conversation_id, task_id, parsed_events
    except Exception as e:
        import traceback
        logger.error("="*60)
        logger.error("WARP API CLIENT EXCEPTION (解析模式)")
        logger.error("="*60)
        logger.error(f"Exception Type: {type(e).__name__}")
        logger.error(f"Exception Message: {str(e)}")
        logger.error(f"Request URL: {warp_url if 'warp_url' in locals() else 'Unknown'}")
        logger.error(f"Request Size: {len(protobuf_bytes) if 'protobuf_bytes' in locals() else 'Unknown'}")
        logger.error("Python Traceback:")
        logger.error(traceback.format_exc())
        logger.error("="*60)
        raise