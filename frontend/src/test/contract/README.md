# Frontend Mock ↔ Schema Contract Tests

此目录集中前端 mock 输出与 Numeric schema 对拍测试。

## 目的

- 后端 pydantic schema 升级 Numeric 时，前端 mock 必须同步升级
- 本目录测试在 CI 中跑，任何 mock shape 漂移都会 fail

## 如何为一个新 mock 方法加对拍

1. 确保 `mockClient.<method>` 已在 Wave 2/3/5 中升级为 Numeric shape
2. 在 `mock-contract.test.ts` 追加一个 `describe` block：

   ```ts
   describe("mockClient.<method>", () => {
     it("returns payload where every Numeric-shaped node passes isNumeric", async () => {
       const client = createApiClient({ mode: "mock" });
       const result = await client.<method>(<params>);
       assertAllNumerics(result);
     });
   });
   ```

3. 在 CI 中 `npm run test -- src/test/contract/` 应自动包含新测试

## 工具

- `assertAllNumerics(payload)` — 递归查找所有"看起来是 Numeric"的子对象，断言 `isNumeric` 全绿；失败时报告精确路径
- `isNumeric(value)` — 定义在 `src/api/numeric.ts`，原子级结构校验

## 与后端 schema 对拍的关系

后端侧由 `tests/test_common_numeric.py` 保证 pydantic `Numeric` shape 正确；前端侧由本目录保证 TS `Numeric` type 与 mock 输出一致；两侧通过**同名字段 + 同 literal 枚举**保持一致性。未来（W5.8）可引入自动 schema 生成消除人工同步。

## 相关设计

`docs/superpowers/specs/2026-04-18-frontend-numeric-correctness-design.md` § 9 / § 10.2
