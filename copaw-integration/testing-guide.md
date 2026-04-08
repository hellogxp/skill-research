# 测试验证指南

> 需要 Python 3.10+ 环境。本地开发机是 Python 3.9.6，无法运行 CoPaw。

## 环境准备

```bash
# 在 Python 3.10+ 的服务器上
git clone https://github.com/hellogxp/CoPaw.git copaw-test
cd copaw-test
git checkout feat/semantic-skill-routing

# 安装 CoPaw + 开发依赖
pip install -e ".[dev,full]"

# 安装语义路由的可选依赖
pip install sentence-transformers faiss-cpu

# 安装 pre-commit hooks
pre-commit install
```

## 测试 1: CoPaw 现有测试回归（最重要）

确保改动没有破坏任何现有功能：

```bash
python -m pytest tests/ -v --tb=short --ignore=tests/test_routing/
```

期望结果：全部 PASSED，没有 FAILED。

## 测试 2: 新功能单元测试

验证 routing 模块自身的逻辑：

```bash
python -m pytest tests/test_routing/ -v --tb=short
```

期望结果：全部 PASSED。

## 测试 3: 零侵入验证

确保不安装可选依赖时 CoPaw 正常工作：

```bash
# 卸载可选依赖
pip uninstall -y sentence-transformers faiss-cpu

# 重新跑 CoPaw 全量测试（含 routing 测试，routing 测试应自动跳过）
python -m pytest tests/ -v --tb=short

# 期望结果：
# - CoPaw 原有测试全部 PASSED
# - routing 测试标记为 SKIPPED（不是 FAILED）
# - 没有 ImportError
```

## 测试 4: pre-commit 代码风格检查

CoPaw PR 必须通过的 CI gate：

```bash
pre-commit run --all-files
```

期望结果：全部 Passed。如果有文件被自动修改，重新 commit 后再跑一次。

## 测试 5: 端到端验证（可选，需要 LLM API key）

真实启动 CoPaw，验证 skill 过滤效果：

```bash
# 重新安装可选依赖
pip install sentence-transformers faiss-cpu

# 初始化并启动
copaw init --defaults
copaw app
```

然后：
1. 打开 Console http://127.0.0.1:8088/
2. Settings 中配置 LLM provider（如 DashScope / OpenAI）
3. 安装 10+ 个 skills
4. 编辑 config.json，在根级别添加：
   ```json
   "semantic_routing": {
     "enabled": true,
     "top_k": 3
   }
   ```
5. 发消息测试
6. 查看 CoPaw 日志，应该能看到类似：
   ```
   Semantic routing: 3/15 skills selected for query: ...
   ```

## 结果反馈

跑完后把以下信息贴回来：
- 测试 1 输出（回归测试）
- 测试 2 输出（新功能测试）
- 测试 3 输出（零侵入验证）
- 测试 4 输出（代码风格）
- 如果有 FAILED，贴完整错误信息
