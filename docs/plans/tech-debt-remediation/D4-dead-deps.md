# D4 死依赖验证与登记：@nextui-org/react、framer-motion

- 登记日期：2026-08-12
- 状态：已验证为死依赖，**尚未卸载**（按规程留待人工执行，本次登记不运行 npm install/uninstall）

## 结论

`@nextui-org/react` 与 `framer-motion` 在 `frontend/src` 及全部构建/样式配置中零引用，判定为死依赖，建议卸载。

## 证据（2026-08-12 复核）

声明位置（`frontend/package.json` dependencies）：

- `"@nextui-org/react": "^2.6.11"`
- `"framer-motion": "^12.42.0"`

引用搜索（含间接引用向量）：

| 检查项 | 命令/方式 | 结果 |
| --- | --- | --- |
| 源码与全部前端文件 | `rg --no-ignore -g '!node_modules' -g '!dist' -g '!coverage' "nextui\|framer-motion" frontend` | 仅命中 `frontend/package.json`（2 处声明）与 `frontend/package-lock.json`（531 处锁文件条目，均为声明的派生物）；`frontend/src`、css `@import`、`index.html` 均为 0 |
| vite 配置 | 同上（覆盖 `frontend/vite.config.ts`、`frontend/vitest.config.ts`） | 零引用 |
| tailwind / postcss 配置 | 枚举 `frontend/` 根目录配置文件 | 项目不存在 tailwind.config.* / postcss.config.*（NextUI 常见的 tailwind 插件接入路径不存在） |
| 反向依赖（锁文件解析） | 解析 `frontend/package-lock.json` 所有 packages 的 dependencies + peerDependencies | 无任何非 `@nextui-org/*` 包依赖 `framer-motion`；无任何包依赖 `@nextui-org/react`。framer-motion 仅作为 @nextui-org 系列的 peer dependency 存在，二者可一并移除 |

## 建议的卸载命令（供人工执行）

```powershell
cd frontend
npm uninstall @nextui-org/react framer-motion
```

卸载后建议验证：

```powershell
npm run build
npm run test
```

## 风险

- 低：零引用 + 无反向依赖，卸载不影响运行时代码路径。
- 唯一影响是 `package-lock.json` 大幅瘦身（约 531 处相关条目移除），属预期收益。
