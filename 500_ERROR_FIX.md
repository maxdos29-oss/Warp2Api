# 🔧 500错误增强处理

## 📋 问题描述

用户报告持续收到500错误：
```
Bridge response: {"response":"❌ Warp API Error (HTTP 500): No error content",...}
```

## 🎯 已实施的改进

### 1. **增强错误日志** ✅

为所有API请求添加了详细的错误日志，包括：
- ❌ 错误状态码
- 📄 错误内容（前500字符）
- 📋 响应头信息
- 📦 请求大小
- 🔄 尝试次数

**修改位置**：
- `warp2protobuf/warp/api_client.py` - `send_protobuf_to_warp_api()` (第101-111行)
- `warp2protobuf/warp/api_client.py` - `send_protobuf_to_warp_api_parsed()` (第314-324行)

**示例日志输出**：
```
❌ Warp API返回错误状态码: 500
   错误内容: No error content
   响应头: {'content-type': 'application/json', ...}
   请求大小: 178 字节
   尝试次数: 1/2
```

### 2. **500错误自动重试** ✅

添加了对500错误的特殊处理：
- 当收到500错误时，自动切换到下一个token
- 刷新新token的JWT
- 使用新token重试请求

**修改位置**：
- `warp2protobuf/warp/api_client.py` - `send_protobuf_to_warp_api()` (第162-176行)
- `warp2protobuf/warp/api_client.py` - `send_protobuf_to_warp_api_parsed()` (第375-389行)

**处理逻辑**：
```python
if response.status_code == 500 and attempt == 0:
    logger.warning("⚠️ WARP API 返回 500 (服务器错误)。尝试切换到下一个token重试…")
    try:
        pool = await get_token_pool()
        token_info = await pool.get_next_token()
        
        if token_info:
            logger.info(f"🔄 切换到token: {token_info.name}")
            # 刷新JWT并重试
            token_data = await refresh_jwt_token_with_token_info(token_info)
            if token_data and "access_token" in token_data:
                jwt = token_data["access_token"]
                logger.info(f"✅ 使用新token重试")
                continue
    except Exception as e:
        logger.error(f"❌ 切换token失败: {e}")
```

## 🔍 500错误可能的原因

### 1. **Token相关问题**
- ✅ **已处理**: 自动切换到下一个token重试
- 可能是某个token被Warp服务器拒绝
- 可能是token权限不足

### 2. **请求数据问题**
- Protobuf数据格式可能有问题
- 某些字段值可能导致服务器崩溃
- 模型配置可能不正确

### 3. **Warp服务器问题**
- 服务器内部错误
- 临时性故障
- 负载过高

### 4. **匿名Token限制**
- 匿名token可能有功能限制
- 某些高级功能可能需要个人token
- **建议**: 如果500错误持续，尝试优先使用个人token

## 📊 错误处理流程

```
请求发送
   ↓
收到500错误
   ↓
记录详细错误信息 ✅
   ↓
第一次尝试? 
   ↓ 是
切换到下一个token ✅
   ↓
刷新JWT
   ↓
重试请求
   ↓
成功? → ✅ 返回结果
   ↓ 否
记录错误并返回 ❌
```

## 🚀 如何验证

### 1. 重启服务器
```bash
# 停止当前服务器 (Ctrl+C)
uv run python server.py
```

### 2. 发送测试请求

当收到500错误时，您会看到：
```
❌ Warp API返回错误状态码: 500
   错误内容: No error content
   响应头: {...}
   请求大小: 178 字节
   尝试次数: 1/2
⚠️ WARP API 返回 500 (服务器错误)。尝试切换到下一个token重试…
🔄 切换到token: PERSONAL_5739
✅ 使用新token重试
```

### 3. 观察结果

**成功场景**：
```
✅ 收到HTTP 200响应
开始处理SSE事件流...
```

**失败场景**：
```
❌ 切换token失败: ...
WARP API HTTP ERROR 500: No error content
```

## 💡 故障排查建议

### 如果500错误持续出现：

#### 1. **检查是否是匿名Token的限制**

匿名token可能有功能限制。尝试临时改回优先使用个人token：

编辑 `warp2protobuf/core/token_pool.py`，将优先级改回：
```python
class TokenPriority(Enum):
    PERSONAL = 1      # 个人token优先
    SHARED = 2
    ANONYMOUS = 3     # 匿名token最后
```

然后在 `get_next_token()` 方法中：
```python
for priority in [TokenPriority.PERSONAL, TokenPriority.SHARED, TokenPriority.ANONYMOUS]:
```

#### 2. **检查请求数据**

查看日志中的请求数据：
```
发送 178 字节到Warp API
数据包前32字节 (hex): 0a26122435366430363265322d...
```

确保：
- 数据大小合理（不是太小或太大）
- Hex数据看起来正常

#### 3. **检查模型配置**

确认使用的模型是有效的：
```json
{
  "model_config": {
    "base": "claude-4.1-opus",
    "planning": "gpt-5 (high reasoning)",
    "coding": "auto"
  }
}
```

尝试使用更基础的模型：
```json
{
  "model_config": {
    "base": "auto",
    "planning": "o3",
    "coding": "auto"
  }
}
```

#### 4. **检查Warp API状态**

访问 https://status.warp.dev 查看是否有服务中断。

#### 5. **查看完整的响应头**

从日志中查看响应头，可能包含有用的错误信息：
```
响应头: {'content-type': 'application/json', 'x-error-code': '...', ...}
```

#### 6. **尝试简化请求**

发送一个最简单的请求：
```json
{
  "input": {
    "user_inputs": {
      "inputs": [
        {
          "user_query": {
            "query": "hello"
          }
        }
      ]
    }
  }
}
```

如果简单请求成功，说明是复杂配置导致的问题。

## 📝 日志分析

### 正常的日志流程：
```
发送 178 字节到Warp API
数据包前32字节 (hex): ...
发送请求到: https://app.warp.dev/ai/multi-agent
✅ 收到HTTP 200响应
开始处理SSE事件流...
收到事件: conversation_id
收到事件: task_id
收到事件: text_delta
...
```

### 500错误的日志流程：
```
发送 178 字节到Warp API
数据包前32字节 (hex): ...
发送请求到: https://app.warp.dev/ai/multi-agent
❌ Warp API返回错误状态码: 500
   错误内容: No error content
   响应头: {...}
   请求大小: 178 字节
   尝试次数: 1/2
⚠️ WARP API 返回 500 (服务器错误)。尝试切换到下一个token重试…
🔄 切换到token: PERSONAL_5739
✅ 使用新token重试
```

## 🎯 预期改进

| 方面 | 修改前 | 修改后 |
|------|--------|--------|
| 错误信息 | 简单 | 详细（状态码、内容、头、大小） |
| 500错误处理 | 直接失败 | 自动切换token重试 |
| 调试能力 | 困难 | 容易（详细日志） |
| 成功率 | 低 | 提高（自动重试） |

## 📖 相关文档

- `TOKEN_PRIORITY_CHANGE.md` - Token优先级变更
- `PRIORITY_CHANGE_SUMMARY.md` - 优先级变更总结
- `ERROR_ANALYSIS.md` - 错误分析报告

---

**修改完成时间**: 2025-10-31  
**修改内容**: 增强500错误日志和自动重试机制  
**影响**: 所有API请求都会有更详细的错误日志，500错误会自动重试

