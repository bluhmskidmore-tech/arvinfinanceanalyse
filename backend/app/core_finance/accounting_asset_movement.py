from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from typing import Literal, Protocol

from backend.app.core_finance.accounting_basis_constants import ACCOUNTING_BASIS_AC

BasisBucket = Literal["AC", "OCI", "TPL"]
# chain_broken 是"横截面对得上、但本月期初接不上上月期末"的判决。它不是第五种
# 头寸 vs 总账差异，而是对 matched 的否决：两个控制里任何一个不过，这一行都不
# 能对外显示成已对平。mismatch / gl_only / zqtz_only 本身已经不是绿灯，信息量
# 也比 chain_broken 更大，所以只降级 matched，其余取值保持不变。
ReconciliationStatus = Literal[
    "matched",
    "mismatch",
    "gl_only",
    "zqtz_only",
    "chain_broken",
]
# no_prior_month 表示没有可比上月（首月，或该分类桶在上月没有落库行），与列值
# 为 NULL（写于本控制落地之前，未记录）语义不同。
ChainStatus = Literal["continuous", "fx_adjusted", "broken", "no_prior_month"]
# 头寸源在该报告日两个候选口径都没有资产行时写入的哨兵值。用显式字符串而不是
# NULL，是为了把它与"旧行未记录"区分开。
POSITION_SOURCE_UNAVAILABLE = "unavailable"

ZERO = Decimal("0")
DEFAULT_TOLERANCE = Decimal("0.01")
# 相对容差：|diff| 必须同时超过绝对下限和 relative_tolerance * max(|gl|, |zqtz|)
# 才判为不平。千亿级余额上 0.01 元的绝对容差没有可操作性，几百亿的口径缺口和
# 一分钱的四舍五入会被同一个阈值处理；相对容差让阈值随头寸规模缩放。
# 1e-6 = 每 100 万元允许 1 元，足以吸收 1700+ 只债券的分位舍入和外币折算尾差。
DEFAULT_RELATIVE_TOLERANCE = Decimal("0.000001")
_BUCKET_ORDER: tuple[BasisBucket, ...] = ("AC", "OCI", "TPL")


def classify_accounting_maturity(
    *, maturity_date: date | None, report_date: date,
    instrument_code: str, bond_type: str, force_unknown: bool = False,
) -> str:
    """公募基金沿用页面 SA/其他 分类；日期缺失不推断逾期或永久期限。"""
    if force_unknown:
        return "unknown"
    if maturity_date is None:
        if instrument_code.startswith("SA") and bond_type == "其他":
            return "fund_no_maturity"
        return "unknown"
    days = (maturity_date - report_date).days
    if days < 0:
        return "overdue_or_matured"
    for limit, bucket in ((30, "<=30d"), (90, "31-90d"), (365, "91d-1y"),
                          (1095, "1-3y"), (1825, "3-5y")):
        if days <= limit:
            return bucket
    return ">5y"


@dataclass(slots=True, frozen=True)
class ZqtzAccountingAssetBalance:
    report_date: date
    accounting_basis: str
    market_value_amount: Decimal
    amortized_cost_amount: Decimal
    position_scope: str = "asset"
    currency_basis: str = "CNY"
    source_version: str = ""
    rule_version: str = ""
    accrued_interest_amount: Decimal = Decimal("0")
    face_value_amount: Decimal = Decimal("0")
    is_voucher_treasury: bool = False


@dataclass(slots=True, frozen=True)
class GlAccountingAssetBalance:
    report_date: date
    account_code: str
    beginning_balance: Decimal
    ending_balance: Decimal
    currency_basis: str = "CNY"
    source_version: str = ""
    rule_version: str = ""


@dataclass(slots=True, frozen=True)
class AccountingAssetMovementRow:
    report_date: date
    report_month: str
    basis_bucket: BasisBucket
    previous_balance: Decimal
    current_balance: Decimal
    balance_change: Decimal
    change_pct: Decimal | None
    contribution_pct: Decimal | None
    zqtz_amount: Decimal
    gl_amount: Decimal
    reconciliation_diff: Decimal
    reconciliation_status: ReconciliationStatus
    source_version: str = ""
    rule_version: str = ""
    chain_status: ChainStatus | None = None
    position_source_basis: str | None = None


@dataclass(slots=True, frozen=True)
class ChainContinuityBreach:
    """跨月勾稽断点：previous_balance(M) 与已落库的 current_balance(M-1) 不相等。

    行内恒等式 balance_change := gl_ending - gl_beginning 在代数上恒成立，
    对"本月期初是否等于上月期末"零覆盖。这个断点是唯一能证伪该口径的信号。
    """

    basis_bucket: BasisBucket
    report_date: date
    prior_report_date: str
    prior_current_balance: Decimal
    reported_previous_balance: Decimal
    gap: Decimal
    tolerance: Decimal


class AccountingAssetMovementSummaryRow(Protocol):
    previous_balance: Decimal
    current_balance: Decimal
    balance_change: Decimal
    zqtz_amount: Decimal
    reconciliation_diff: Decimal
    reconciliation_status: ReconciliationStatus


@dataclass(slots=True, frozen=True)
class AccountingAssetMovementSummary:
    previous_balance_total: Decimal
    current_balance_total: Decimal
    balance_change_total: Decimal
    zqtz_amount_total: Decimal
    reconciliation_diff_total: Decimal
    matched_bucket_count: int
    bucket_count: int


@dataclass(slots=True, frozen=True)
class UnmappedGlAccount:
    """144 科目前缀既未映射到 OCI 桶、也不在已知排除前缀内的科目。"""

    account_code: str
    beginning_balance: Decimal
    ending_balance: Decimal


@dataclass(slots=True, frozen=True)
class AccountingAssetMovementBuildResult:
    """分类桶行 + 144 家族未映射披露；迭代/下标兼容既有 list 用法。"""

    rows: list[AccountingAssetMovementRow]
    unmapped_gl_accounts: tuple[UnmappedGlAccount, ...] = ()

    def __iter__(self):
        return iter(self.rows)

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> AccountingAssetMovementRow:
        return self.rows[index]


def build_accounting_asset_movement_rows(
    *,
    report_date: date,
    zqtz_rows: list[ZqtzAccountingAssetBalance],
    gl_rows: list[GlAccountingAssetBalance],
    tolerance: Decimal = DEFAULT_TOLERANCE,
    relative_tolerance: Decimal = DEFAULT_RELATIVE_TOLERANCE,
    position_source_available: bool = True,
    position_source_basis: str | None = None,
    excluded_gl_account_prefixes: Sequence[str] = (),
) -> AccountingAssetMovementBuildResult:
    """把独立头寸源（zqtz_rows）与总账控制科目（gl_rows）对账成分类桶月度行。

    zqtz_rows 必须来自独立于 gl_rows 的头寸系统。两侧取自同一张总账表时
    diff 恒为 0，reconciliation_status 恒为 matched，对账退化成自我比对。

    position_source_available=False 表示头寸源当期整体缺失（表不存在 / 该
    报告日无行），此时禁止判 matched：两侧同时为 0 的"假平"正是
    reconciliation_checks 在 2026-07-19 已经修掉的同一类缺陷。

    position_source_basis 是头寸侧实际命中的折算口径（例如 'CNY'），落到行上
    供读取端判断 zqtz_amount / reconciliation_diff 是否有对手方支撑。缺失当期
    统一写 POSITION_SOURCE_UNAVAILABLE；调用方不传则留 None（未记录）。

    excluded_gl_account_prefixes 是已知排除的科目前缀（如 '144020'），由调用
    方传入；core_finance 不引用 service 常量。这些科目不进任何分类桶，也不
    进入未映射披露。144 前缀、既非 1440101 也非排除前缀的科目同样不进桶，
    但会出现在 unmapped_gl_accounts。
    """
    resolved_position_basis = (
        position_source_basis if position_source_available else POSITION_SOURCE_UNAVAILABLE
    )
    zqtz_amounts = {bucket: ZERO for bucket in _BUCKET_ORDER}
    gl_beginning = {bucket: ZERO for bucket in _BUCKET_ORDER}
    gl_ending = {bucket: ZERO for bucket in _BUCKET_ORDER}
    source_versions: list[str] = []
    rule_versions: list[str] = []

    for row in zqtz_rows:
        if row.report_date != report_date or row.position_scope != "asset":
            continue
        bucket = _bucket_from_accounting_basis(row.accounting_basis)
        if bucket is None:
            continue
        principal = (
            row.amortized_cost_amount if bucket == ACCOUNTING_BASIS_AC else row.market_value_amount
        )
        # 与本页明细金额一致：凭证式国债未提供估值时按面值补本金，利息另加。
        if row.is_voucher_treasury and principal == ZERO:
            principal = row.market_value_amount or row.face_value_amount
        zqtz_amounts[bucket] += principal + row.accrued_interest_amount
        _append_unique(source_versions, row.source_version)
        _append_unique(rule_versions, row.rule_version)

    dated_gl_rows = [row for row in gl_rows if row.report_date == report_date]
    for gl_row in dated_gl_rows:
        bucket = _bucket_from_gl_account(gl_row.account_code)
        if bucket is None:
            continue
        gl_beginning[bucket] += gl_row.beginning_balance
        gl_ending[bucket] += gl_row.ending_balance
        _append_unique(source_versions, gl_row.source_version)
        _append_unique(rule_versions, gl_row.rule_version)

    changes = {
        bucket: gl_ending[bucket] - gl_beginning[bucket]
        for bucket in _BUCKET_ORDER
    }
    total_abs_change = sum((abs(value) for value in changes.values()), ZERO)

    rows: list[AccountingAssetMovementRow] = []
    for bucket in _BUCKET_ORDER:
        beginning = gl_beginning[bucket]
        ending = gl_ending[bucket]
        change = changes[bucket]
        zqtz_amount = zqtz_amounts[bucket]
        diagnostic_diff = zqtz_amount - ending
        rows.append(
            AccountingAssetMovementRow(
                report_date=report_date,
                report_month=f"{report_date:%Y-%m}",
                basis_bucket=bucket,
                previous_balance=beginning,
                current_balance=ending,
                balance_change=change,
                change_pct=_pct(change, beginning),
                contribution_pct=_pct(abs(change), total_abs_change),
                zqtz_amount=zqtz_amount,
                gl_amount=ending,
                reconciliation_diff=diagnostic_diff,
                reconciliation_status=_reconciliation_status(
                    zqtz_amount=zqtz_amount,
                    gl_amount=ending,
                    diff=diagnostic_diff,
                    tolerance=effective_tolerance(
                        left=zqtz_amount,
                        right=ending,
                        absolute_tolerance=tolerance,
                        relative_tolerance=relative_tolerance,
                    ),
                    position_source_available=position_source_available,
                ),
                source_version="__".join(source_versions),
                rule_version="__".join(rule_versions),
                position_source_basis=resolved_position_basis,
            )
        )
    return AccountingAssetMovementBuildResult(
        rows=rows,
        unmapped_gl_accounts=collect_unmapped_gl144_accounts(
            dated_gl_rows,
            excluded_gl_account_prefixes=excluded_gl_account_prefixes,
        ),
    )


def build_accounting_asset_movement_summary(
    rows: Iterable[AccountingAssetMovementSummaryRow],
) -> AccountingAssetMovementSummary:
    materialized_rows = tuple(rows)
    return AccountingAssetMovementSummary(
        previous_balance_total=sum(
            (row.previous_balance for row in materialized_rows),
            ZERO,
        ),
        current_balance_total=sum(
            (row.current_balance for row in materialized_rows),
            ZERO,
        ),
        balance_change_total=sum(
            (row.balance_change for row in materialized_rows),
            ZERO,
        ),
        zqtz_amount_total=sum(
            (row.zqtz_amount for row in materialized_rows),
            ZERO,
        ),
        reconciliation_diff_total=sum(
            (row.reconciliation_diff for row in materialized_rows),
            ZERO,
        ),
        matched_bucket_count=sum(
            1
            for row in materialized_rows
            if row.reconciliation_status == "matched"
        ),
        bucket_count=len(materialized_rows),
    )


def effective_tolerance(
    *,
    left: Decimal,
    right: Decimal,
    absolute_tolerance: Decimal = DEFAULT_TOLERANCE,
    relative_tolerance: Decimal = DEFAULT_RELATIVE_TOLERANCE,
) -> Decimal:
    """绝对下限与相对容差取大者。相对部分以两侧绝对值的较大者为基数，
    这样任一侧为 0（单边有值）时容差不会塌回绝对下限之外。"""
    scale = max(abs(left), abs(right))
    return max(absolute_tolerance, relative_tolerance * scale)


def evaluate_chain_continuity(
    *,
    rows: Iterable[AccountingAssetMovementRow],
    prior_report_date: str | None,
    prior_current_balances: Mapping[str, Decimal],
    tolerance: Decimal = DEFAULT_TOLERANCE,
    relative_tolerance: Decimal = DEFAULT_RELATIVE_TOLERANCE,
    fx_adjustments: Mapping[str, Decimal] | None = None,
) -> list[ChainContinuityBreach]:
    """校验 previous_balance(M) == current_balance(M-1)。

    prior_report_date 为 None（无上月落库行）时返回空列表：没有可比基准，
    不能因此判定断裂。
    """
    if prior_report_date is None:
        return []

    breaches: list[ChainContinuityBreach] = []
    for row in rows:
        if row.basis_bucket not in prior_current_balances:
            continue
        prior_balance = prior_current_balances[row.basis_bucket]
        gap = row.previous_balance - prior_balance - (fx_adjustments or {}).get(row.basis_bucket, ZERO)
        bucket_tolerance = effective_tolerance(
            left=row.previous_balance,
            right=prior_balance,
            absolute_tolerance=tolerance,
            relative_tolerance=relative_tolerance,
        )
        if abs(gap) <= bucket_tolerance:
            continue
        breaches.append(
            ChainContinuityBreach(
                basis_bucket=row.basis_bucket,
                report_date=row.report_date,
                prior_report_date=prior_report_date,
                prior_current_balance=prior_balance,
                reported_previous_balance=row.previous_balance,
                gap=gap,
                tolerance=bucket_tolerance,
            )
        )
    return breaches


def apply_chain_continuity_status(
    rows: Iterable[AccountingAssetMovementRow],
    *,
    breaches: Iterable[ChainContinuityBreach],
    prior_report_date: str | None,
    prior_current_balances: Mapping[str, Decimal],
    fx_adjustments: Mapping[str, Decimal] | None = None,
) -> list[AccountingAssetMovementRow]:
    """把跨月勾稽判决写进行里，并否决"断裂却仍显示已对平"的行。

    判定口径与 evaluate_chain_continuity 完全对齐（含"上月没有这个分类桶就不
    判定"的跳过规则），因此 chain_status 永远解释得清 breaches 为什么是那样。
    reconciliation_status 只在原本是 matched 时降级为 chain_broken：mismatch /
    gl_only / zqtz_only 已经不是绿灯，且比 chain_broken 更能说明差异来源。
    """
    broken_buckets = {breach.basis_bucket for breach in breaches}
    updated: list[AccountingAssetMovementRow] = []
    for row in rows:
        if prior_report_date is None or row.basis_bucket not in prior_current_balances:
            chain_status: ChainStatus = "no_prior_month"
        elif row.basis_bucket in broken_buckets:
            chain_status = "broken"
        elif (fx_adjustments or {}).get(row.basis_bucket, ZERO) != ZERO:
            chain_status = "fx_adjusted"
        else:
            chain_status = "continuous"
        reconciliation_status: ReconciliationStatus = (
            "chain_broken"
            if chain_status == "broken" and row.reconciliation_status == "matched"
            else row.reconciliation_status
        )
        updated.append(
            replace(
                row,
                chain_status=chain_status,
                reconciliation_status=reconciliation_status,
            )
        )
    return updated


def reconcile_chain_fx_adjustments(
    *,
    current_gl: Sequence[GlAccountingAssetBalance],
    prior_gl: Sequence[GlAccountingAssetBalance],
    prior_rate: Decimal,
    current_rate: Decimal,
) -> dict[str, Decimal]:
    """仅解释逐科目可闭合的单一外币折算；不以桶净额抵销真实断点。

    调用方须验证独立头寸源只含一种外币，且两个月正式汇率齐备。
    CNX/CNY 两侧必须逐键覆盖、人民币余额衔接，折算残差不超过一分。
    任一科目不满足则整桶保留原始勾稽判定，禁止反推差额充当汇率。
    """
    if prior_rate <= ZERO or current_rate <= ZERO or prior_rate == current_rate:
        return {}
    current = {(r.account_code, r.currency_basis): r for r in current_gl}
    prior = {(r.account_code, r.currency_basis): r for r in prior_gl}
    if len(current) != len(current_gl) or len(prior) != len(prior_gl):
        return {}
    adjustments: dict[str, Decimal] = {}
    invalid: set[str] = set()
    codes = {code for code, currency in current.keys() | prior.keys() if currency == "CNX"}
    for code in codes:
        bucket = _bucket_from_gl_account(code)
        if bucket is None:
            continue
        sides = (current.get((code, "CNX")), prior.get((code, "CNX")),
                 current.get((code, "CNY")), prior.get((code, "CNY")))
        if any(row is None for row in sides):
            invalid.add(bucket)
            continue
        now, before, now_cny, before_cny = sides
        assert now is not None and before is not None and now_cny is not None and before_cny is not None
        domestic_gap = now_cny.beginning_balance - before_cny.ending_balance
        expected_fx = (before.ending_balance - before_cny.ending_balance) * (current_rate / prior_rate - 1)
        gap = now.beginning_balance - before.ending_balance
        if abs(domestic_gap) > DEFAULT_TOLERANCE or abs(gap - expected_fx) > DEFAULT_TOLERANCE:
            invalid.add(bucket)
        adjustments[bucket] = adjustments.get(bucket, ZERO) + expected_fx
    return {bucket: amount for bucket, amount in adjustments.items() if bucket not in invalid and amount != ZERO}


def _bucket_from_accounting_basis(value: str) -> BasisBucket | None:
    normalized = str(value or "").strip().upper()
    if normalized in {"AC", "H"}:
        return "AC"
    if normalized in {"FVOCI", "OCI", "A"}:
        return "OCI"
    if normalized in {"FVTPL", "TPL", "T"}:
        return "TPL"
    return None


def _bucket_from_gl_account(account_code: str) -> BasisBucket | None:
    code = str(account_code or "").strip()
    if code.startswith("141"):
        return "TPL"
    if code.startswith(("142", "143")):
        return "AC"
    if code.startswith("1440101"):
        return "OCI"
    return None


def _is_unmapped_gl144(
    account_code: str,
    excluded_gl_account_prefixes: Sequence[str],
) -> bool:
    code = str(account_code or "").strip()
    if not code.startswith("144"):
        return False
    if code.startswith("1440101"):
        return False
    return not any(
        code.startswith(str(prefix).strip())
        for prefix in excluded_gl_account_prefixes
        if str(prefix).strip()
    )


def collect_unmapped_gl144_accounts(
    gl_rows: Iterable[GlAccountingAssetBalance],
    *,
    excluded_gl_account_prefixes: Sequence[str] = (),
) -> tuple[UnmappedGlAccount, ...]:
    """汇总 144 前缀、既非 1440101 也非已知排除前缀的科目金额。不进入分类桶。"""
    totals: dict[str, tuple[Decimal, Decimal]] = {}
    for row in gl_rows:
        code = str(row.account_code or "").strip()
        if not _is_unmapped_gl144(code, excluded_gl_account_prefixes):
            continue
        beginning, ending = totals.get(code, (ZERO, ZERO))
        totals[code] = (
            beginning + row.beginning_balance,
            ending + row.ending_balance,
        )
    return tuple(
        UnmappedGlAccount(
            account_code=code,
            beginning_balance=beginning,
            ending_balance=ending,
        )
        for code, (beginning, ending) in sorted(totals.items())
    )


def _reconciliation_status(
    *,
    zqtz_amount: Decimal,
    gl_amount: Decimal,
    diff: Decimal,
    tolerance: Decimal,
    position_source_available: bool = True,
) -> ReconciliationStatus:
    if not position_source_available:
        # 头寸源整体缺失：没有对手方就没有"平"。gl_only 是现有词汇里唯一
        # 诚实的表达，绝不能因为两侧都是 0 而落到 matched。
        return "gl_only"
    if abs(diff) <= tolerance:
        return "matched"
    if gl_amount == ZERO:
        return "zqtz_only"
    if zqtz_amount == ZERO:
        return "gl_only"
    return "mismatch"


def _pct(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    if denominator == ZERO:
        return None
    return numerator / abs(denominator) * Decimal("100")


def _append_unique(items: list[str], value: str) -> None:
    normalized = str(value or "").strip()
    if normalized and normalized not in items:
        items.append(normalized)


__all__ = [
    "DEFAULT_RELATIVE_TOLERANCE",
    "DEFAULT_TOLERANCE",
    "POSITION_SOURCE_UNAVAILABLE",
    "AccountingAssetMovementBuildResult",
    "AccountingAssetMovementRow",
    "AccountingAssetMovementSummary",
    "BasisBucket",
    "ChainContinuityBreach",
    "ChainStatus",
    "GlAccountingAssetBalance",
    "ReconciliationStatus",
    "UnmappedGlAccount",
    "ZqtzAccountingAssetBalance",
    "apply_chain_continuity_status",
    "build_accounting_asset_movement_rows",
    "build_accounting_asset_movement_summary",
    "collect_unmapped_gl144_accounts",
    "effective_tolerance",
    "evaluate_chain_continuity",
]
