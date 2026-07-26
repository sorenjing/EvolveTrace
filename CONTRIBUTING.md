# 贡献指南

感谢你对 EvolveLab 的兴趣！这是一个个人维护的开源项目，欢迎通过 Issue 和 PR 参与建设。

> 在贡献之前，请先阅读 [README](README.md) 了解项目定位，阅读 [RUN.md](RUN.md) 在本地跑起来，阅读 [DESIGN.md](DESIGN.md) 了解架构。

---

## 行为准则

请保持友善与尊重。对新手友好——这是一个**研究型 Coding Agent 源码项目**，目标用户包含学习者和想理解 Agent 机制的开发者。任何形式的歧视、攻击、骚扰言行都不被接受。

---

## 开发环境

```bash
# 后端
cd backend
python -m venv venv
.\venv\Scripts\activate        # Windows  | source venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
uvicorn main:app --port 8001 --reload

# 前端
npm install
npm run dev
```

详细说明见 [RUN.md](RUN.md)。

---

## 提交 Issue

### Bug 报告

请使用 Bug 模板（`.github/ISSUE_TEMPLATE/bug_report.md`），并包含：

1. **复现步骤**：明确的操作顺序
2. **预期行为** vs **实际行为**
3. **环境信息**：操作系统、Python 版本、Node 版本、浏览器
4. **日志 / 截图**：后端日志、前端 Console 报错、Timeline 截图

### 功能建议

请使用 Feature 模板（`.github/ISSUE_TEMPLATE/feature_request.md`），并说明：

1. **使用场景**：你想解决什么问题？
2. **当前方案**：现在你怎么绕过这个限制？
3. **期望方案**：你希望它怎么工作？

> 重大改动建议先开 Discussion 或 Issue 讨论，避免做了大改动后被否。

---

## 提交 PR

### 流程

1. Fork 本仓库
2. 创建分支：`git checkout -b feat/your-feature` 或 `fix/your-bugfix`
3. 提交修改，commit 信息清晰（见下方规范）
4. 推到自己的 fork：`git push origin feat/your-feature`
5. 在 GitHub 上发起 Pull Request，目标分支 `master`
6. 在 PR 描述里关联相关 Issue（如 `Closes #12`）

### 提交前自检

**必做**：

```bash
# 后端语法检查
cd backend
python -m py_compile $(Get-ChildItem -Recurse -Include *.py | Select-Object -ExpandProperty FullName)
# macOS/Linux: python -m py_compile $(find . -name "*.py")

# 前端构建
cd ..
npm run build
```

**鼓励做**：

- 后端：`pytest`（如果有测试）
- 前端：`npm run lint`

### Commit 信息规范

格式：`<type>: <简短描述>`

**type** 可选值：

- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档变更
- `refactor`: 重构（不改功能、不修 Bug）
- `perf`: 性能优化
- `test`: 测试相关
- `chore`: 构建 / 配置 / 杂项

示例：

```
feat: 新增 Timeline 步骤折叠功能
fix: 修复暗黑模式切换后水合警告
docs: 补充非商用许可证说明
refactor: 抽离 services 层
```

### 代码风格

- **Python**：遵循 `black` + `isort`（配置见 `backend/pyproject.toml`）
- **TypeScript/React**：遵循 `prettier`（配置见 `.prettierrc`）
- **命名**：Python 用 snake_case，TypeScript 用 camelCase，组件用 PascalCase
- **注释**：复杂逻辑必加注释，简单逻辑不必

---

## 安全注意事项

1. **绝不提交真实 API Key、密码、密钥**
2. **不提交 `.env` 文件**（已在 `.gitignore` 中忽略）
3. 如发现安全漏洞，**请勿公开 Issue**，邮件或私密联系作者

---

## License

提交的代码将在 [PolyForm Noncommercial License 1.0.0](LICENSE) 下发布。提交 PR 即表示你同意该许可。

---

## 其他

- **响应时间**：个人维护，通常 3 天内响应 Issue/PR
- **范围控制**：保持项目精简，避免引入过重依赖
- **不接收的 PR**：
  - 引入大型框架（如 Django、Express）替换现有技术栈
  - 与项目定位（可观测性、工具扩展、安全边界）不符的功能
  - 大幅改动现有 API 协议但不提供迁移方案的

再次感谢你的贡献！
