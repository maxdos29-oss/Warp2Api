# 更新日志 - 多Token功能

## [新功能] 2025-10-31 - 多Refresh Token支持

### 🎉 主要更新

添加了多refresh token支持，实现智能负载均衡和自动故障转移。

### ✨ 新增功能

#### 1. Token池管理系统
- **三级优先级策略**：个人token > 共享token > 匿名token
- **智能轮换机制**：同优先级token自动round-robin轮换
- **自动故障转移**：token失败时自动切换到下一个可用token
- **失败计数和禁用**：失败3次后自动禁用token
- **健康监控**：实时监控所有token的健康状态
- **自动恢复**：支持手动或自动恢复失败的token

#### 2. 配置支持
- **WARP_REFRESH_TOKEN**：单个个人token（向后兼容）
- **WARP_PERSONAL_TOKENS**：多个个人tokens（逗号分隔）
- **WARP_SHARED_TOKENS**：共享tokens（逗号分隔）
- **WARP_ANONYMOUS_TOKEN**：匿名token（可选，有内置后备）

#### 3. API增强
- `refresh_jwt_token()`：使用token池刷新JWT
- `refresh_jwt_token_with_token_info()`：使用指定token刷新
- `print_token_pool_info()`：显示token池信息
- `check_token_pool_health()`：健康检查
- `recover_failed_tokens()`：恢复失败的tokens

### 📁 新增文件

1. **warp2protobuf/core/token_pool.py** (343行)
   - TokenPool类：核心token池管理器
   - TokenInfo类：token信息数据类
   - TokenPriority枚举：优先级定义

2. **test_token_pool.py** (260行)
   - 完整的测试套件
   - 7个测试用例，全部通过

3. **demo_multi_token.py** (240行)
   - 交互式演示脚本
   - 7个演示场景

4. **.env.multi-token.example** (120行)
   - 详细的配置示例
   - 包含多种使用场景

5. **docs/MULTI_TOKEN_GUIDE.md** (300行)
   - 完整的使用指南
   - 配置示例和最佳实践
   - 故障排除和API参考

6. **MULTI_TOKEN_IMPLEMENTATION.md** (280行)
   - 实现总结文档
   - 技术细节和架构说明

### 🔧 修改的文件

1. **warp2protobuf/core/auth.py**
   - 导入token_pool模块
   - 重构refresh_jwt_token()使用token池
   - 添加多个新的辅助函数

2. **.env.example**
   - 添加多token配置说明
   - 添加优先级说明和示例

3. **warp2protobuf/config/settings.py**
   - 添加WARP_PERSONAL_TOKENS配置
   - 添加WARP_SHARED_TOKENS配置
   - 添加WARP_ANONYMOUS_TOKEN配置

4. **README.md**
   - 添加"多Token配置"章节
   - 更新环境变量表格
   - 更新认证说明
   - 添加工作流程说明

### 🎯 使用示例

#### 基础配置
```env
WARP_REFRESH_TOKEN=your_personal_token
```

#### 多token配置
```env
WARP_PERSONAL_TOKENS=token1,token2,token3
WARP_SHARED_TOKENS=shared1,shared2
```

#### 完整配置
```env
WARP_REFRESH_TOKEN=my_token
WARP_PERSONAL_TOKENS=token2,token3
WARP_SHARED_TOKENS=team1,team2,team3
WARP_ANONYMOUS_TOKEN=fallback
```

### 🧪 测试

运行测试套件：
```bash
uv run python test_token_pool.py
```

运行演示：
```bash
uv run python demo_multi_token.py
```

### 📊 测试结果

所有7个测试用例通过：
- ✅ Token Pool Initialization
- ✅ Priority-based Selection
- ✅ Round-robin Rotation
- ✅ Token Refresh
- ✅ Health Check
- ✅ Failure Handling
- ✅ Pool Information

### 🔄 向后兼容性

- ✅ 完全兼容现有配置
- ✅ 单token配置仍然有效
- ✅ 无需修改现有代码
- ✅ 自动使用内置匿名token作为后备

### 💡 优势

1. **高可用性**：多个tokens确保服务持续可用
2. **负载均衡**：自动轮换tokens，避免单点过载
3. **优先级控制**：个人tokens优先使用
4. **自动故障转移**：token失败时自动切换
5. **易于管理**：简单的环境变量配置
6. **实时监控**：健康检查和状态监控

### 📚 文档

- **快速开始**：README.md
- **详细指南**：docs/MULTI_TOKEN_GUIDE.md
- **配置示例**：.env.multi-token.example
- **实现总结**：MULTI_TOKEN_IMPLEMENTATION.md

### 🎓 最佳实践

1. **个人使用**：配置1-2个个人tokens
2. **小团队**：配置2-5个个人tokens
3. **大团队**：配置个人 + 共享 + 匿名tokens
4. **高可用**：配置尽可能多的tokens，定期监控

### 🐛 已知问题

无

### 🔮 未来计划

- [ ] 添加token使用统计
- [ ] 添加token自动轮换策略配置
- [ ] 添加Web界面管理token池
- [ ] 添加token性能监控

### 👥 贡献者

- 实现：AI Assistant
- 测试：完整测试套件
- 文档：完整文档和示例

---

## 如何升级

1. 拉取最新代码
2. 查看 `.env.multi-token.example` 了解新配置选项
3. 根据需要更新 `.env` 文件
4. 运行测试验证：`uv run python test_token_pool.py`
5. 启动服务，查看日志确认token池初始化

## 获取帮助

- 查看 `docs/MULTI_TOKEN_GUIDE.md` 获取详细指南
- 运行 `uv run python demo_multi_token.py` 查看演示
- 查看 `MULTI_TOKEN_IMPLEMENTATION.md` 了解技术细节

