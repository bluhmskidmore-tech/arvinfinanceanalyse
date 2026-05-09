/**
 * 从本机 MOSS API 拉取「业务种类损益」数据，写入当前用户桌面 Excel。
 * 用法（在 frontend 目录）:
 *   node scripts/export_pnl_by_business_desktop.mjs
 * 环境变量:
 *   MOSS_API_BASE — API 根地址，默认依次尝试 http://127.0.0.1:7888 与 http://127.0.0.1:5888
 *   MOSS_REPORT_DATE — 可选，固定报表日 YYYY-MM-DD（不填则用 /api/pnl/dates 最新日）
 */
import fs from "node:fs";
import path from "node:path";
import XLSX from "xlsx";

const WAN = 10_000;
const YI = 100_000_000;

function num(v) {
  if (v === null || v === undefined || v === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

function wan(v) {
  const n = num(v);
  return n === null ? null : n / WAN;
}

function yi(v) {
  const n = num(v);
  return n === null ? null : n / YI;
}

async function tryFetch(url) {
  const res = await fetch(url, { headers: { Accept: "application/json" } });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status} ${url}\n${text.slice(0, 500)}`);
  }
  return res.json();
}

async function resolveApiBase() {
  if (process.env.MOSS_API_BASE) {
    return process.env.MOSS_API_BASE.replace(/\/$/, "");
  }
  const candidates = ["http://127.0.0.1:7888", "http://127.0.0.1:5888"];
  for (const base of candidates) {
    try {
      const j = await tryFetch(`${base}/health`);
      if (j && typeof j === "object") {
        return base;
      }
    } catch {
      /* try next */
    }
  }
  for (const base of candidates) {
    try {
      await tryFetch(`${base}/api/pnl/dates`);
      return base;
    } catch {
      /* try next */
    }
  }
  throw new Error(
    `无法连接 API，已尝试: ${candidates.join(", ")}。请启动后端（默认 7888）或带 /api 代理的前端（5888），或设置 MOSS_API_BASE。`,
  );
}

function sheetFromAoA(name, aoa) {
  const ws = XLSX.utils.aoa_to_sheet(aoa);
  return { name: name.slice(0, 31), ws };
}

function desktopPath(filename) {
  const desk =
    process.env.USERPROFILE && fs.existsSync(path.join(process.env.USERPROFILE, "Desktop"))
      ? path.join(process.env.USERPROFILE, "Desktop")
      : process.env.USERPROFILE
        ? path.join(process.env.USERPROFILE, "OneDrive", "Desktop")
        : process.cwd();
  return path.join(desk, filename);
}

async function main() {
  const base = await resolveApiBase();
  const datesEnvelope = await tryFetch(`${base}/api/pnl/dates`);
  const datesPayload = datesEnvelope.result ?? datesEnvelope;
  const reportDate =
    process.env.MOSS_REPORT_DATE?.trim() ||
    datesPayload.formal_fi_report_dates?.[0] ||
    datesPayload.report_dates?.[0];
  if (!reportDate) {
    throw new Error("未拿到可用报表日：/api/pnl/dates 返回为空。请检查库内是否有 formal 数据。");
  }
  const year = Number(String(reportDate).slice(0, 4));
  if (!Number.isFinite(year)) {
    throw new Error(`报表日格式异常: ${reportDate}`);
  }

  const ytdEnvelope = await tryFetch(
    `${base}/api/pnl/by-business-ytd?year=${year}&as_of_date=${encodeURIComponent(reportDate)}`,
  );
  const ytd = ytdEnvelope.result ?? ytdEnvelope;
  const items = Array.isArray(ytd.items) ? ytd.items : [];

  let monthly = { months: [] };
  try {
    const mEnv = await tryFetch(
      `${base}/api/pnl/by-business-monthly?year=${year}&as_of_date=${encodeURIComponent(reportDate)}`,
    );
    monthly = mEnv.result ?? mEnv;
  } catch (e) {
    console.warn("月度接口跳过:", e.message);
  }

  const wb = XLSX.utils.book_new();

  const meta = [
    ["业务种类损益 — 桌面导出（脚本）"],
    ["API", base],
    ["报表截止日", reportDate],
    ["年度", year],
    ["YTD 区间", `${ytd.period_start_date ?? ""} ~ ${ytd.period_end_date ?? ""}`],
    ["说明", "金额列：万元 = 接口元 / 10000；亿元 = 元 / 1e8"],
    [],
  ];
  XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(meta), "导出说明");

  const ytdHeader = [
    "业务种类",
    "利息收入(万元)",
    "公允价值变动(万元)",
    "资本利得(万元)",
    "手工调整(万元)",
    "合计损益(万元)",
    "期末余额(亿元)",
    "占比(0-1)",
    "资产数",
    "row_key",
  ];
  const ytdRows = [ytdHeader];
  for (const row of items) {
    ytdRows.push([
      row.business_type,
      wan(row.interest_income),
      wan(row.fair_value_change),
      wan(row.capital_gain),
      wan(row.manual_adjustment),
      wan(row.total_pnl),
      yi(row.current_balance),
      num(row.proportion),
      row.assets_count,
      row.row_key,
    ]);
  }
  XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(ytdRows), "YTD年累计");

  const months = Array.isArray(monthly.months) ? monthly.months : [];
  const monHeader = [
    "月份",
    "区间起",
    "区间止",
    "业务种类",
    "日均(亿元)",
    "期末余额(亿元)",
    "利息收入(万元)",
    "公允价值变动(万元)",
    "资本利得(万元)",
    "手工调整(万元)",
    "合计损益(万元)",
    "年化收益率(%)",
    "FTP后收益(万元)",
    "FTP后收益率(%)",
    "占比(0-1)",
    "资产数",
  ];
  const monRows = [monHeader];
  for (const m of months) {
    for (const row of m.items || []) {
      monRows.push([
        m.month_key,
        m.period_start_date,
        m.period_end_date,
        row.business_type,
        yi(row.avg_balance),
        yi(row.current_balance),
        wan(row.interest_income),
        wan(row.fair_value_change),
        wan(row.capital_gain),
        wan(row.manual_adjustment),
        wan(row.total_pnl),
        num(row.annualized_yield_pct),
        wan(row.ftp_net_pnl),
        num(row.ftp_net_annualized_yield_pct),
        num(row.proportion),
        row.asset_count,
      ]);
    }
  }
  if (monRows.length > 1) {
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(monRows), "月度业务种类");
  }

  const filename = `业务种类损益_${reportDate}_YTD_桌面导出.xlsx`;
  const out = desktopPath(filename);
  XLSX.writeFile(wb, out);
  console.log("已写入:", out);
}

main().catch((err) => {
  console.error(err.message || err);
  process.exit(1);
});
