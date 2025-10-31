# 🔄 Token优先级策略变更

## 📋 变更说明

根据用户要求，已将Token Pool的优先级策略调整为**优先使用匿名Token**，以节省个人Token的配额。

## 🎯 新的优先级顺序

### 之前的策略（已废弃）
```
1. 个人Token (PERSONAL) - 最高优先级
2. 共享Token (SHARED) - 中等优先级  
3. 匿名Token (ANONYMOUS) - 最低优先级
```

**问题**: 这会快速消耗个人Token的配额，而匿名Token的配额没有被充分利用。

### 当前策略（已实施）✅
```
1. 匿名Token (ANONYMOUS) - 最高优先级 ⭐
2. 共享Token (SHARED) - 中等优先级
3. 个人Token (PERSONAL) - 最低优先级（保底使用）
```

**优势**: 
- ✅ 优先消耗匿名Token的配额
- ✅ 节省个人Token配额用于关键时刻
- ✅ 当匿名Token配额用尽时，自动切换到个人Token
- ✅ 实现配额的最优利用

## 🔧 修改的文件

### 1. `warp2protobuf/core/token_pool.py`

#### 修改1: TokenPriority枚举
```python
class TokenPriority(Enum):
    """Token priority levels"""
    ANONYMOUS = 1     # Anonymous tokens (highest priority - to save personal quota)
    SHARED = 2        # Shared tokens (medium priority)
    PERSONAL = 3      # Personal tokens (lowest priority - save for when anonymous fails)
```

#### 修改2: 初始化顺序
```python
# Load anonymous/fallback token (highest priority - to save personal quota)
anonymous_token = self._load_anonymous_token()
if anonymous_token:
    self._add_token_internal(anonymous_token, TokenPriority.ANONYMOUS)

# Load shared tokens (medium priority)
shared_tokens = self._load_shared_tokens()
for token in shared_tokens:
    self._add_token_internal(token, TokenPriority.SHARED)

# Load personal tokens (lowest priority - save for when anonymous fails)
personal_tokens = self._load_personal_tokens()
for token in personal_tokens:
    self._add_token_internal(token, TokenPriority.PERSONAL)
```

#### 修改3: get_next_token方法
```python
# Try each priority level in order (ANONYMOUS first to save personal quota)
for priority in [TokenPriority.ANONYMOUS, TokenPriority.SHARED, TokenPriority.PERSONAL]:
    token = self._get_token_by_priority(priority)
    if token:
        token.last_used = time.time()
        logger.debug(f"🎯 Selected token: {token.name} (priority: {priority.name})")
        return token
```

#### 修改4: 日志显示顺序
```python
# Show in priority order (ANONYMOUS first)
for priority in [TokenPriority.ANONYMOUS, TokenPriority.SHARED, TokenPriority.PERSONAL]:
    count = sum(1 for t in self._tokens if t.priority == priority and t.is_active)
    if count > 0:
        by_priority[priority.name] = count

priority_str = ", ".join(f"{k}: {v}" for k, v in by_priority.items())
logger.info(f"📊 Token Pool: {active}/{total} active tokens (优先级: {priority_str})")
```

### 2. `server.py`

#### 修改: 启动信息显示
```python
logger.info(f"✅ Token Pool已初始化 (优先使用匿名Token以节省个人配额)")
logger.info(f"   📊 总Token数: {stats['total_tokens']}")
logger.info(f"   ✅ 活跃Token数: {stats['active_tokens']}")
logger.info(f"   ❌ 失败Token数: {stats['failed_tokens']}")
logger.info(f"   ")
logger.info(f"   使用优先级 (从高到低):")
logger.info(f"   1️⃣  匿名Token数: {stats['anonymous_tokens']} (最优先)")
logger.info(f"   2️⃣  共享Token数: {stats['shared_tokens']}")
logger.info(f"   3️⃣  个人Token数: {stats['personal_tokens']} (保底使用)")
```

## 📊 工作流程示例

### 场景1: 正常使用（匿名Token可用）
```
1. 用户发送请求
2. Token Pool选择匿名Token
3. 使用匿名Token发送请求
4. 请求成功 ✅
5. 个人Token配额得到保留 💰
```

### 场景2: 匿名Token配额用尽
```
1. 用户发送请求
2. Token Pool选择匿名Token
3. 使用匿名Token发送请求
4. 收到429错误（配额用尽）
5. Token Pool自动切换到个人Token
6. 使用个人Token重试请求
7. 请求成功 ✅
```

### 场景3: 所有Token配额用尽
```
1. 用户发送请求
2. Token Pool尝试匿名Token → 429错误
3. Token Pool尝试共享Token → 429错误（如果有）
4. Token Pool尝试个人Token → 429错误
5. 所有Token都失败
6. 返回错误给用户 ❌
```

## 🎯 预期效果

### 配额使用优化

| Token类型 | 之前 | 现在 | 改进 |
|-----------|------|------|------|
| 匿名Token | 很少使用 | 优先使用 | ⬆️ 利用率提升 |
| 个人Token | 快速消耗 | 保底使用 | ⬇️ 消耗减少 |
| 总体可用性 | 中等 | 高 | ⬆️ 显著提升 |

### 用户体验

- ✅ **透明切换**: 用户无感知，自动选择最优Token
- ✅ **配额节省**: 个人Token配额得到保护
- ✅ **高可用性**: 多层次的failover机制
- ✅ **智能管理**: 自动处理配额用尽的情况

## 🚀 如何验证

### 1. 重启服务器
```bash
# 停止当前服务器 (Ctrl+C)
# 重新启动
uv run python server.py
```

### 2. 查看启动日志
应该看到类似输出：
```
✅ Token Pool已初始化 (优先使用匿名Token以节省个人配额)
   📊 总Token数: 2
   ✅ 活跃Token数: 2
   ❌ 失败Token数: 0
   
   使用优先级 (从高到低):
   1️⃣  匿名Token数: 1 (最优先)
   2️⃣  共享Token数: 0
   3️⃣  个人Token数: 1 (保底使用)
```

### 3. 发送测试请求
观察日志中的Token选择：
```
🎯 Selected token: ANONYMOUS_1234 (priority: ANONYMOUS)
```

### 4. 触发配额切换
当匿名Token配额用尽时，应该看到：
```
⚠️ WARP API 返回 429 (配额用尽)。尝试从token pool获取下一个token并重试…
✅ 使用token pool中的下一个token: PERSONAL_5739
```

## 📝 配置说明

### 环境变量（.env文件）

```env
# 个人Token（现在作为保底使用）
WARP_REFRESH_TOKEN='your_personal_token_here'

# 多个个人Token（可选，逗号分隔）
WARP_PERSONAL_TOKENS='token2,token3'

# 共享Token（可选）
WARP_SHARED_TOKENS='shared_token1,shared_token2'

# 匿名Token（内置，自动加载，优先使用）
# 无需配置，系统自动使用内置的匿名Token
```

## 💡 最佳实践

### 1. 配置建议
- ✅ 保留至少1个个人Token作为保底
- ✅ 让系统自动使用内置的匿名Token
- ✅ 如有多个账号，可配置多个个人Token

### 2. 监控建议
- 📊 定期查看Token使用情况
- 📊 关注匿名Token的配额重置时间
- 📊 监控个人Token的使用频率

### 3. 故障处理
- 🔧 如果匿名Token失效，系统会自动切换到个人Token
- 🔧 如果所有Token都失败，检查配额重置时间
- 🔧 可以添加更多个人Token来提高可用性

## 🔗 相关文档

- `MULTI_TOKEN_SETUP.md` - 多Token配置指南
- `BUGFIX_SUMMARY.md` - Bug修复总结
- `ERROR_ANALYSIS.md` - 错误分析报告

## 📞 技术支持

如果遇到问题：
1. 检查启动日志中的Token Pool状态
2. 确认Token配置正确
3. 查看API请求日志中的Token选择信息
4. 参考相关文档进行故障排查

---

**变更日期**: 2025-10-31  
**变更原因**: 用户要求优先使用匿名Token以节省个人配额  
**影响范围**: Token选择逻辑、日志显示、启动信息  
**向后兼容**: ✅ 完全兼容，无需修改配置文件

