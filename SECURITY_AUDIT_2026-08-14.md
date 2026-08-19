# 静态安全审计（2026-08-18 更新）

本次记录已由 Codex Security 运行时扫描补充：扫描覆盖
`implementation/agent_world_model` 的 53 个运行时文件，完整报告保存在本机
Codex Security scan artifact 目录。生成报告前发现的候选均完成了源代码验证和
攻击路径复核；论文不属于本次安全工作范围。

## 已修复

1. **远程推理端点缺少边界限制**：客户端过去接受任意 HTTP URL，可能将任务
   状态和页面内容发送至非预期公网服务。现在只允许 HTTPS，或显式的回环/私网
   HTTP 端点；禁止 URL 中携带凭据、查询参数、片段和额外路径。
2. **推理服务无鉴权**：现在支持通过 `AGENT_WORLD_MODEL_AUTH_TOKEN` 启用
   Bearer 鉴权，使用常量时间比较；客户端从同名环境变量读取，不把 token 写进
   配置或 URL。默认仍绑定 `127.0.0.1`。
3. **并发推理可破坏可复现性并放大资源消耗**：服务明确只支持单并发配置，
   请求体继续限制为 2 MB。
4. **安全边界缺少仓库级说明**：新增 `SECURITY.md`，记录端点、凭据、模型权重、
   轨迹与冻结证据的不变量。
5. **评估器 checkpoint 不安全反序列化**：`evaluate_phase3_multistep.py` 现在
   使用 `weights_only=True` 并校验维度和 tensor-only `state_dict`。
6. **推理服务的可达绑定保护**：非回环绑定现在强制 Bearer token 和 TLS；服务改为
   单线程 `HTTPServer`，使单并发约束与实现一致。
7. **研究文本和远程边界加固**：人工审阅 CSV 对公式前缀做中和，动作校验拒绝
   多调用拼接，远程响应体限制为 2 MB，限流桶增加过期回收和客户端上限。

## 已核对的有效控制

- 候选动作由动作模式和当前 AXTree 可见元素 ID 双重验证。
- PyTorch checkpoint 使用 `torch.load(..., weights_only=True)`。
- 未发现仓库源代码中硬编码的 SSH 密码、API key 或 Bearer token。
- 外部命令使用列表参数调用；未发现 `shell=True`、`os.system` 或对页面文本执行
  `eval/exec` 的路径。

## 剩余风险

- 回环绑定仍允许省略 token，这是为本地 SSH 隧道保留的部署模式；任何非回环绑定
  都由启动检查强制 token 和 TLS。
- 生产部署仍应由反向代理执行更严格的速率限制和日志脱敏。
- 轨迹包含页面文本和任务内容，应按研究数据管理，不上传含真实账号、cookie 或
  私密页面的轨迹。

## 验证

- 端点校验、私网/HTTPS 允许规则、Bearer 头部行为已加入单元测试。
- 本轮相关测试 31 项通过；修改文件通过 `py_compile` 和 `git diff --check`。
