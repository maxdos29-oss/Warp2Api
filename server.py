#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Warp Protobuf编解码服务器启动文件

纯protobuf编解码服务器，提供JSON<->Protobuf转换、WebSocket监控和静态文件服务。
"""

import os
import asyncio
import json
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi import Query, HTTPException
from fastapi.responses import Response
# 新增：类型导入
from typing import Any, Dict, List

from warp2protobuf.api.protobuf_routes import app as protobuf_app
from warp2protobuf.core.logging import logger, set_log_file
from warp2protobuf.api.protobuf_routes import EncodeRequest, _encode_smd_inplace
from warp2protobuf.core.protobuf_utils import dict_to_protobuf_bytes
from warp2protobuf.core.schema_sanitizer import sanitize_mcp_input_schema_in_packet
from warp2protobuf.core.auth import acquire_anonymous_access_token
from warp2protobuf.config.models import get_all_unique_models


# ============= 工具：input_schema 清理与校验 =============

def _is_empty_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    if isinstance(value, (list, dict)) and len(value) == 0:
        return True
    return False


def _deep_clean(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: Dict[str, Any] = {}
        for k, v in value.items():
            vv = _deep_clean(v)
            if _is_empty_value(vv):
                continue
            cleaned[k] = vv
        return cleaned
    if isinstance(value, list):
        cleaned_list = []
        for item in value:
            ii = _deep_clean(item)
            if _is_empty_value(ii):
                continue
            cleaned_list.append(ii)
        return cleaned_list
    if isinstance(value, str):
        return value.strip()
    return value


def _infer_type_for_property(prop_name: str) -> str:
    name = prop_name.lower()
    if name in ("url", "uri", "href", "link"):
        return "string"
    if name in ("headers", "options", "params", "payload", "data"):
        return "object"
    return "string"


def _ensure_property_schema(name: str, schema: Dict[str, Any]) -> Dict[str, Any]:
    prop = dict(schema) if isinstance(schema, dict) else {}
    prop = _deep_clean(prop)

    # 必填：type & description
    if "type" not in prop or not isinstance(prop.get("type"), str) or not prop["type"].strip():
        prop["type"] = _infer_type_for_property(name)
    if "description" not in prop or not isinstance(prop.get("description"), str) or not prop["description"].strip():
        prop["description"] = f"{name} parameter"

    # 特殊处理 headers：必须是对象，且其 properties 不能是空
    if name.lower() == "headers":
        prop["type"] = "object"
        headers_props = prop.get("properties")
        if not isinstance(headers_props, dict):
            headers_props = {}
        headers_props = _deep_clean(headers_props)
        if not headers_props:
            headers_props = {
                "user-agent": {
                    "type": "string",
                    "description": "User-Agent header for the request",
                }
            }
        else:
            # 清理并保证每个 header 的子属性都具备 type/description
            fixed_headers: Dict[str, Any] = {}
            for hk, hv in headers_props.items():
                sub = _deep_clean(hv if isinstance(hv, dict) else {})
                if "type" not in sub or not isinstance(sub.get("type"), str) or not sub["type"].strip():
                    sub["type"] = "string"
                if "description" not in sub or not isinstance(sub.get("description"), str) or not sub["description"].strip():
                    sub["description"] = f"{hk} header"
                fixed_headers[hk] = sub
            headers_props = fixed_headers
        prop["properties"] = headers_props
        # 处理 required 空数组
        if isinstance(prop.get("required"), list):
            req = [r for r in prop["required"] if isinstance(r, str) and r in headers_props]
            if req:
                prop["required"] = req
            else:
                prop.pop("required", None)
        # additionalProperties 若为空 dict，删除；保留显式 True/False
        if isinstance(prop.get("additionalProperties"), dict) and len(prop["additionalProperties"]) == 0:
            prop.pop("additionalProperties", None)

    return prop


def _sanitize_json_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    s = _deep_clean(schema if isinstance(schema, dict) else {})

    # 如果存在 properties，则顶层应为 object
    if "properties" in s and not isinstance(s.get("type"), str):
        s["type"] = "object"

    # 修正 $schema
    if "$schema" in s and not isinstance(s["$schema"], str):
        s.pop("$schema", None)
    if "$schema" not in s:
        s["$schema"] = "http://json-schema.org/draft-07/schema#"

    properties = s.get("properties")
    if isinstance(properties, dict):
        fixed_props: Dict[str, Any] = {}
        for name, subschema in properties.items():
            fixed_props[name] = _ensure_property_schema(name, subschema if isinstance(subschema, dict) else {})
        s["properties"] = fixed_props

    # required：去掉不存在的属性，且不允许为空列表
    if isinstance(s.get("required"), list):
        if isinstance(properties, dict):
            req = [r for r in s["required"] if isinstance(r, str) and r in properties]
        else:
            req = []
        if req:
            s["required"] = req
        else:
            s.pop("required", None)

    # additionalProperties：空 dict 视为无效，删除
    if isinstance(s.get("additionalProperties"), dict) and len(s["additionalProperties"]) == 0:
        s.pop("additionalProperties", None)

    return s


class _InputSchemaSanitizerMiddleware:  # deprecated; use sanitize_mcp_input_schema_in_packet in handlers
    pass


# ============= 应用创建 =============

def create_app() -> FastAPI:
    """创建FastAPI应用"""
    # 将服务器日志重定向到专用文件
    try:
        set_log_file('warp_server.log')
    except Exception:
        pass
    
    # 使用protobuf路由的应用作为主应用
    app = protobuf_app

    # 挂载输入 schema 清理中间件（覆盖 Warp 相关端点）

    
    # 检查静态文件目录
    static_dir = Path("static")
    if static_dir.exists():
        # 挂载静态文件服务
        app.mount("/static", StaticFiles(directory="static"), name="static")
        logger.info("✅ 静态文件服务已启用: /static")
        
        # 添加根路径重定向到前端界面
        @app.get("/gui", response_class=HTMLResponse)
        async def serve_gui():
            """提供前端GUI界面"""
            index_file = static_dir / "index.html"
            if index_file.exists():
                return HTMLResponse(content=index_file.read_text(encoding='utf-8'))
            else:
                return HTMLResponse(content="""
                <html>
                    <body>
                        <h1>前端界面文件未找到</h1>
                        <p>请确保 static/index.html 文件存在</p>
                    </body>
                </html>
                """)
    else:
        logger.warning("静态文件目录不存在，GUI界面将不可用")
        
        @app.get("/gui", response_class=HTMLResponse)
        async def no_gui():
            return HTMLResponse(content="""
            <html>
                <body>
                    <h1>GUI界面未安装</h1>
                    <p>静态文件目录 'static' 不存在</p>
                    <p>请创建前端界面文件</p>
                </body>
            </html>
            """)

    # ============= 新增接口：返回protobuf编码后的AI请求字节 =============
    @app.post("/api/warp/encode_raw")
    async def encode_ai_request_raw(
        request: EncodeRequest,
        output: str = Query("raw", description="输出格式：raw(默认，返回application/x-protobuf字节) 或 base64", regex=r"^(raw|base64)$"),
    ):
        try:
            # 获取实际数据并验证
            actual_data = request.get_data()
            if not actual_data:
                raise HTTPException(400, "数据包不能为空")

            # 在 encode 之前，对 mcp_context.tools[*].input_schema 做一次安全清理
            if isinstance(actual_data, dict):
                wrapped = {"json_data": actual_data}
                wrapped = sanitize_mcp_input_schema_in_packet(wrapped)
                actual_data = wrapped.get("json_data", actual_data)

            # 将 server_message_data 对象（如有）编码为 Base64URL 字符串
            actual_data = _encode_smd_inplace(actual_data)

            # 编码为protobuf字节
            protobuf_bytes = dict_to_protobuf_bytes(actual_data, request.message_type)
            logger.info(f"✅ AI请求编码为protobuf成功: {len(protobuf_bytes)} 字节")

            if output == "raw":
                # 直接返回二进制 protobuf 内容
                return Response(
                    content=protobuf_bytes,
                    media_type="application/x-protobuf",
                    headers={"Content-Length": str(len(protobuf_bytes))},
                )
            else:
                # 返回base64文本，便于在JSON中传输/调试
                import base64
                return {
                    "protobuf_base64": base64.b64encode(protobuf_bytes).decode("utf-8"),
                    "size": len(protobuf_bytes),
                    "message_type": request.message_type,
                }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ AI请求编码失败: {e}")
            raise HTTPException(500, f"编码失败: {str(e)}")
    
    # ============= OpenAI 兼容：模型列表接口 =============
    @app.get("/v1/models")
    async def list_models():
        """OpenAI-compatible endpoint that lists available models."""
        try:
            models = get_all_unique_models()
            return {"object": "list", "data": models}
        except Exception as e:
            logger.error(f"❌ 获取模型列表失败: {e}")
            raise HTTPException(500, f"获取模型列表失败: {str(e)}")
    
    return app


############################################################
# server_message_data 深度编解码工具
############################################################

# 说明：
# 根据抓包与分析，server_message_data 是 Base64URL 编码的 proto3 消息：
#   - 字段 1：string（通常为 36 字节 UUID）
#   - 字段 3：google.protobuf.Timestamp（字段1=seconds，字段2=nanos）
# 可能出现：仅 Timestamp、仅 UUID、或 UUID + Timestamp。

from typing import Dict, Optional, Tuple
import base64
from datetime import datetime, timezone
try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except Exception:
    ZoneInfo = None  # type: ignore


def _b64url_decode_padded(s: str) -> bytes:
    t = s.replace("-", "+").replace("_", "/")
    pad = (-len(t)) % 4
    if pad:
        t += "=" * pad
    return base64.b64decode(t)


def _b64url_encode_nopad(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("ascii").rstrip("=")


def _read_varint(buf: bytes, i: int) -> Tuple[int, int]:
    shift = 0
    val = 0
    while i < len(buf):
        b = buf[i]
        i += 1
        val |= (b & 0x7F) << shift
        if not (b & 0x80):
            return val, i
        shift += 7
        if shift > 63:
            break
    raise ValueError("invalid varint")


def _write_varint(v: int) -> bytes:
    out = bytearray()
    vv = int(v)
    while True:
        to_write = vv & 0x7F
        vv >>= 7
        if vv:
            out.append(to_write | 0x80)
        else:
            out.append(to_write)
            break
    return bytes(out)


def _make_key(field_no: int, wire_type: int) -> bytes:
    return _write_varint((field_no << 3) | wire_type)


def _decode_timestamp(buf: bytes) -> Tuple[Optional[int], Optional[int]]:
    # google.protobuf.Timestamp: field 1 = seconds (int64 varint), field 2 = nanos (int32 varint)
    i = 0
    seconds: Optional[int] = None
    nanos: Optional[int] = None
    while i < len(buf):
        key, i = _read_varint(buf, i)
        field_no = key >> 3
        wt = key & 0x07
        if wt == 0:  # varint
            val, i = _read_varint(buf, i)
            if field_no == 1:
                seconds = int(val)
            elif field_no == 2:
                nanos = int(val)
        elif wt == 2:  # length-delimited (not expected inside Timestamp)
            ln, i2 = _read_varint(buf, i)
            i = i2 + ln
        elif wt == 1:
            i += 8
        elif wt == 5:
            i += 4
        else:
            break
    return seconds, nanos


def _encode_timestamp(seconds: Optional[int], nanos: Optional[int]) -> bytes:
    parts = bytearray()
    if seconds is not None:
        parts += _make_key(1, 0)  # field 1, varint
        parts += _write_varint(int(seconds))
    if nanos is not None:
        parts += _make_key(2, 0)  # field 2, varint
        parts += _write_varint(int(nanos))
    return bytes(parts)


def decode_server_message_data(b64url: str) -> Dict:
    """解码 Base64URL 的 server_message_data，返回结构化信息。"""
    try:
        raw = _b64url_decode_padded(b64url)
    except Exception as e:
        return {"error": f"base64url decode failed: {e}", "raw_b64url": b64url}

    i = 0
    uuid: Optional[str] = None
    seconds: Optional[int] = None
    nanos: Optional[int] = None

    while i < len(raw):
        key, i = _read_varint(raw, i)
        field_no = key >> 3
        wt = key & 0x07
        if wt == 2:  # length-delimited
            ln, i2 = _read_varint(raw, i)
            i = i2
            data = raw[i:i+ln]
            i += ln
            if field_no == 1:  # uuid string
                try:
                    uuid = data.decode("utf-8")
                except Exception:
                    uuid = None
            elif field_no == 3:  # google.protobuf.Timestamp
                seconds, nanos = _decode_timestamp(data)
        elif wt == 0:  # varint -> not expected, skip
            _, i = _read_varint(raw, i)
        elif wt == 1:
            i += 8
        elif wt == 5:
            i += 4
        else:
            break

    out: Dict[str, Any] = {}
    if uuid is not None:
        out["uuid"] = uuid
    if seconds is not None:
        out["seconds"] = seconds
    if nanos is not None:
        out["nanos"] = nanos
    return out


def encode_server_message_data(uuid: str = None, seconds: int = None, nanos: int = None) -> str:
    """将 uuid/seconds/nanos 组合编码为 Base64URL 字符串。"""
    parts = bytearray()
    if uuid:
        b = uuid.encode("utf-8")
        parts += _make_key(1, 2)  # field 1, length-delimited
        parts += _write_varint(len(b))
        parts += b

    if seconds is not None or nanos is not None:
        ts = _encode_timestamp(seconds, nanos)
        parts += _make_key(3, 2)  # field 3, length-delimited
        parts += _write_varint(len(ts))
        parts += ts

    return _b64url_encode_nopad(bytes(parts))


async def startup_tasks():
    """启动时执行的任务"""
    logger.info("="*60)
    logger.info("Warp Protobuf编解码服务器启动")
    logger.info("="*60)
    
    # 检查protobuf运行时
    try:
        from warp2protobuf.core.protobuf import ensure_proto_runtime
        ensure_proto_runtime()
        logger.info("✅ Protobuf运行时初始化成功")
    except Exception as e:
        logger.error(f"❌ Protobuf运行时初始化失败: {e}")
        raise
    
    # 初始化并显示Token Pool信息
    try:
        from warp2protobuf.core.token_pool import get_token_pool
        from warp2protobuf.core.auth import print_token_pool_info

        logger.info("="*60)
        logger.info("🔐 初始化Token Pool...")
        pool = await get_token_pool()
        stats = await pool.get_pool_stats()

        logger.info(f"✅ Token Pool已初始化 (优先使用匿名Token以节省个人配额)")
        logger.info(f"   📊 总Token数: {stats['total_tokens']}")
        logger.info(f"   ✅ 活跃Token数: {stats['active_tokens']}")
        logger.info(f"   ❌ 失败Token数: {stats['failed_tokens']}")
        logger.info(f"   ")
        logger.info(f"   使用优先级 (从高到低):")
        logger.info(f"   1️⃣  匿名Token数: {stats['anonymous_tokens']} (最优先)")
        logger.info(f"   2️⃣  共享Token数: {stats['shared_tokens']}")
        logger.info(f"   3️⃣  个人Token数: {stats['personal_tokens']} (保底使用)")

        # 显示详细的token信息
        await print_token_pool_info()
        logger.info("="*60)

    except Exception as e:
        logger.warning(f"⚠️ Token Pool初始化失败: {e}")

    # 检查JWT token
    try:
        from warp2protobuf.core.auth import get_jwt_token, is_token_expired
        token = get_jwt_token()
        if token and not is_token_expired(token):
            logger.info("✅ JWT token有效")
        elif not token:
            logger.warning("⚠️ 未找到JWT token，尝试申请匿名访问token用于额度初始化…")
            try:
                new_token = await acquire_anonymous_access_token()
                if new_token:
                    logger.info("✅ 匿名访问token申请成功")
                else:
                    logger.warning("⚠️ 匿名访问token申请失败")
            except Exception as e2:
                logger.warning(f"⚠️ 匿名访问token申请异常: {e2}")
        else:
            logger.warning("⚠️ JWT token无效或已过期，建议运行: uv run refresh_jwt.py")
    except Exception as e:
        logger.warning(f"⚠️ JWT检查失败: {e}")
    
    # 如需 OpenAI 兼容层，请单独运行 src/openai_compat_server.py
    
    # 显示可用端点
    logger.info("-"*40)
    logger.info("可用的API端点:")
    logger.info("  GET  /                   - 服务信息")
    logger.info("  GET  /healthz            - 健康检查")
    logger.info("  GET  /gui                - Web GUI界面")
    logger.info("  POST /api/encode         - JSON -> Protobuf编码")
    logger.info("  POST /api/decode         - Protobuf -> JSON解码")
    logger.info("  POST /api/stream-decode  - 流式protobuf解码")
    logger.info("  POST /api/warp/send      - JSON -> Protobuf -> Warp API转发")
    logger.info("  POST /api/warp/send_stream - JSON -> Protobuf -> Warp API转发(返回解析事件)")
    logger.info("  POST /api/warp/send_stream_sse - JSON -> Protobuf -> Warp API转发(实时SSE，事件已解析)")
    logger.info("  POST /api/warp/graphql/* - GraphQL请求转发到Warp API（带鉴权）")
    logger.info("  GET  /api/schemas        - Protobuf schema信息")
    logger.info("  GET  /api/auth/status    - JWT认证状态")
    logger.info("  POST /api/auth/refresh   - 刷新JWT token")
    logger.info("  GET  /api/auth/user_id   - 获取当前用户ID")
    logger.info("  GET  /api/packets/history - 数据包历史记录")
    logger.info("  WS   /ws                 - WebSocket实时监控")
    logger.info("-"*40)
    logger.info("测试命令:")
    logger.info("  uv run main.py --test basic    - 运行基础测试")
    logger.info("  uv run main.py --list          - 查看所有测试场景")
    logger.info("="*60)


def main():
    """主函数"""
    import argparse
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="Warp Protobuf编解码服务器")
    parser.add_argument("--port", type=int, default=28888, help="服务器监听端口 (默认: 28888)")
    args = parser.parse_args()
    
    # 创建应用
    app = create_app()
    
    # 添加启动事件
    @app.on_event("startup")
    async def startup_event():
        await startup_tasks()
    
    # 启动服务器
    try:
        logger.info(f"启动服务器在端口 {args.port}")
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=args.port,
            log_level="info",
            access_log=True
        )
    except KeyboardInterrupt:
        logger.info("服务器被用户停止")
    except Exception as e:
        logger.error(f"服务器启动失败: {e}")
        raise


if __name__ == "__main__":
    main()
