let neutralFixtureSeq = 0;

export type NeutralDrilldownFixture = Readonly<{
  /** 测试侧可读标签，不映射任何 API 字段名 */
  label: string;
  /** 单调递增的测试用标识，不映射任何服务端 id 语义 */
  seq: number;
}>;

/**
 * 生成与后端契约无关的占位数据，仅用于在测试中区分多份「尚未定义的」上下文。
 */
export function createNeutralDrilldownFixture(label = "neutral"): NeutralDrilldownFixture {
  return Object.freeze({ label, seq: ++neutralFixtureSeq });
}

/**
 * 重置序号（可选）：在需要完全隔离的单测文件里于 beforeEach 中调用。
 */
export function resetNeutralDrilldownFixtureSeq(): void {
  neutralFixtureSeq = 0;
}
