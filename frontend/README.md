# MOSS 前端开发

日常开发在 [5890 源码预览](http://127.0.0.1:5890/) 查看当前工作区，修改后由 Vite 热更新。[5888](http://127.0.0.1:5888/) 查看已登记的构建版本，5889 留给自动化测试。

## 启动热更新

在 `frontend/` 执行：

```sh
npm run dev:source
```

该命令使用跨平台 Node 入口 `scripts/dev-frontend-source.mjs`，通过现有 `dev_runtime_control.py` 复用维护标记、操作锁、路径检查和子进程管理。源码预览只监听 `127.0.0.1:5890`，端口已占用时直接报错；需要其它端口时执行 `npm run dev:source -- --port 5891`，5888 和 5889 仍受保护。启动不切换 5888 的运行登记。默认使用真实数据，并将现有 API 路径代理到本地 `127.0.0.1:7888`；沿用已有环境配置与后端权限，不为预览另开匿名权限或 mock 回退。显式设置 `VITE_DATA_SOURCE=mock` 时，入口会打印所选模式。

环境沿用 Python 3.11、Node 22 和现有锁文件。入口先核对已有的 `MOSS_PYTHON` 或 `VIRTUAL_ENV` 显式选择；显式环境失效或版本不符时直接报错。没有显式选择时，依次寻找 `backend/.venv`、根 `.venv` 中适合当前平台的 Python 3.11，Windows 使用 `Scripts/python.exe`，Linux 使用 `bin/python`，并打印实际解释器路径和版本。入口不调用未经核对的全局 `python`。若依赖未准备好，按 [锁定安装说明](../docs/DEVELOPMENT.md#锁定安装与源码预览) 准备项目环境。

Windows 后端尚未启动时，复用仓库 `scripts/dev-api.ps1`；Linux 的现有 Compose 地址与宿主源码预览不同，配置和联通边界见 [容器开发入口](../docs/DEVELOPMENT.md#容器开发入口)。测试实例需要显式使用隔离样本。旧 `scripts/dev-frontend-source.ps1` 是 Windows 兼容入口，保留 `-Port` 参数并转发到同一个 Node 启动器。

开发进程需要保持运行，结束时在启动它的终端按 `Ctrl+C`。维护标记仍会阻止启动；重启电脑后重新执行上面的命令即可。

## 运行局部检查

在仓库根目录执行下面的示例，只验证首页分布映射及其组件：

```powershell
powershell -NoProfile -File .\scripts\codex-verify-page.ps1 `
  -PageSlug dashboard-home -FrontendFeedback `
  -FrontendTests "src/features/workbench/dashboard-home/dashboardHomeBodyView.test.ts,src/features/workbench/dashboard-home/DashboardHomeOptionTwoLayout.test.tsx" `
  -LintFiles "src/features/workbench/dashboard-home/dashboardHomeBodyView.ts,src/features/workbench/dashboard-home/DashboardHomeOptionTwoLayout.tsx" `
  -Run
```

文件路径相对 `frontend/`，多个文件以逗号分隔。需要类型检查时追加 `-Typecheck`，省略 `-Run` 先查看计划。脚本集中执行所选检查，并打印各项结果和耗时；这些结果可在当前改动和环境未变化时复用。局部反馈不自动执行后端、MCP、债务审计、构建或整页验收。

验证范围以 [frontend/AGENTS.md](AGENTS.md) 为准。首页模块与测试入口见 [首页维护说明](src/features/workbench/dashboard-home/README.md)，视觉实现按 [DESIGN.md](../DESIGN.md)。完整验收和正式交接仍使用各自已有入口。

同一批相关测试可合并到一次 `-FrontendTests` 调用。只执行已核对名称的用例时，追加 `-FrontendTestNamePattern`，值为 Vitest 测试全名匹配正则；该参数要求同时提供明确测试文件。性能对比可追加 `-FrontendTestSerial`，固定一个 worker 并串行执行文件；省略时沿用现有 Vitest 并发设置。名称筛选和串行选项只适用于 `-FrontendFeedback` 或指定文件的 `-HomeFeedback`，不改变完整页面核验和 CI 默认集合。
