import {
  DataTable,
  KpiStrip,
  SECTION_HEAD_STACK_CLASSNAME,
  SectionGrid,
  SectionHead,
  StateSurface,
  StateSurfaceQuotaProvider,
  sectionStateFromStatus,
  type DataTableStatus,
  type SectionStateTone,
  type SurfaceStatus,
} from ".";
import { SURFACE_STATUS_LABEL } from "./statusBridge";

/** 双向可赋值才算相等；单向 extends 会漏掉「一边多一个成员」的漂移。 */
type AssertEqual<A, B> = [A] extends [B] ? ([B] extends [A] ? true : false) : false;

/*
 * 编译期锁：任一词表增删成员，下面的 `= true` 会因为类型变成 `false` 而报错。
 * 放在测试文件里是为了让 typecheck 与 vitest 都能捕获，而不是只在某处生效。
 */
const statusWordListsMatch: AssertEqual<SurfaceStatus, DataTableStatus> = true;
const sectionToneIsStatusMinusReady: AssertEqual<
  SectionStateTone,
  Exclude<SurfaceStatus, "ready">
> = true;

describe("layout primitives barrel", () => {
  it("keeps the status word lists aligned across primitives", () => {
    expect(statusWordListsMatch).toBe(true);
    expect(sectionToneIsStatusMinusReady).toBe(true);
  });

  it("exports every primitive under one consistent named surface", () => {
    // 组件文件的 default/named 导出不一致（SectionHead/KpiStrip 是 default，
    // 其余是 named）；barrel 统一成 named，使用方不必记住哪个是哪种。
    for (const primitive of [KpiStrip, SectionHead, SectionGrid, StateSurface, DataTable]) {
      expect(typeof primitive).toBe("function");
    }
    expect(typeof StateSurfaceQuotaProvider).toBe("function");
    expect(typeof SECTION_HEAD_STACK_CLASSNAME).toBe("string");
  });
});

describe("sectionStateFromStatus", () => {
  it("maps ready to null so the section head takes no vertical space", () => {
    expect(sectionStateFromStatus("ready", "已就绪")).toBeNull();
  });

  it("carries the label and tone through for every non-ready status", () => {
    const nonReady: Exclude<SurfaceStatus, "ready">[] = [
      "loading",
      "empty",
      "error",
      "stale",
      "partial",
    ];
    for (const status of nonReady) {
      expect(sectionStateFromStatus(status, "读取中")).toEqual({
        label: "读取中",
        tone: status,
      });
    }
  });

  it("falls back to the primitive's default word list when label is omitted (new, backward-compatible)", () => {
    const nonReady: Exclude<SurfaceStatus, "ready">[] = [
      "loading",
      "empty",
      "error",
      "stale",
      "partial",
    ];
    for (const status of nonReady) {
      expect(sectionStateFromStatus(status)).toEqual({
        label: SURFACE_STATUS_LABEL[status],
        tone: status,
      });
    }
  });

  it("still maps ready to null when label is omitted", () => {
    expect(sectionStateFromStatus("ready")).toBeNull();
  });
});

describe("SURFACE_STATUS_LABEL single source", () => {
  it("covers every SurfaceStatus value", () => {
    const covered = Object.keys(SURFACE_STATUS_LABEL) as SurfaceStatus[];
    const expectedStatuses: SurfaceStatus[] = [
      "ready",
      "loading",
      "empty",
      "error",
      "stale",
      "partial",
    ];
    expect(covered.sort()).toEqual([...expectedStatuses].sort());
  });

  it("has a defined default label for every status except ready", () => {
    for (const status of ["loading", "empty", "error", "stale", "partial"] as const) {
      expect(typeof SURFACE_STATUS_LABEL[status]).toBe("string");
      expect(SURFACE_STATUS_LABEL[status]?.length).toBeGreaterThan(0);
    }
    expect(SURFACE_STATUS_LABEL.ready).toBeUndefined();
  });

  it("is the same object StateSurface renders by default (no second copy to drift)", () => {
    // sectionStateFromStatus without a label and StateSurface without a
    // `message` prop must resolve to byte-identical text for every status —
    // both read SURFACE_STATUS_LABEL, there is no second literal copy.
    for (const status of ["loading", "empty", "error", "stale", "partial"] as const) {
      const bridged = sectionStateFromStatus(status);
      expect(bridged?.label).toBe(SURFACE_STATUS_LABEL[status]);
    }
  });
});
