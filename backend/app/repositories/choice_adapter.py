from dataclasses import dataclass

from backend.app.config.choice_runtime import _get_em_c, configure_emquant_parent, load_settings
from backend.app.repositories.choice_client import ChoiceClient
from backend.app.schemas.macro_vendor import (
    ChoiceMacroSeriesConfig,
    ChoiceMacroPoint,
    ChoiceMacroSnapshot,
)
from backend.app.schemas.vendor import (
    VendorAdapter as VendorAdapterBase,
    VendorPreflightResult,
    VendorSnapshot,
)


@dataclass
class VendorAdapter(VendorAdapterBase):
    vendor_name: str = "choice"

    def preflight(self) -> VendorPreflightResult:
        settings = load_settings()
        if not settings.choice_emquant_parent:
            return VendorPreflightResult(
                vendor_name=self.vendor_name,
                ok=False,
                status="missing_config",
                detail="CHOICE_EMQUANT_PARENT or config/settings.yaml: choice.emquant_parent must be set before live fetch is enabled.",
            )
        if not settings.choice_start_options:
            return VendorPreflightResult(
                vendor_name=self.vendor_name,
                ok=False,
                status="missing_config",
                detail="CHOICE_MACRO_CHOICE_START_OPTIONS or config/settings.yaml: choice.start_options must be set before live fetch is enabled.",
            )
        configure_emquant_parent(settings.choice_emquant_parent)
        if _get_em_c() is None:
            return VendorPreflightResult(
                vendor_name=self.vendor_name,
                ok=False,
                status="missing_config",
                detail="EmQuantAPI.c could not be imported from the configured parent directory.",
            )

        return VendorPreflightResult(
            vendor_name=self.vendor_name,
            ok=True,
            status="config_present",
            detail="EmQuant runtime path and start options are present.",
        )

    def fetch_snapshot(self) -> VendorSnapshot:
        return VendorSnapshot(
            vendor_name=self.vendor_name,
            vendor_version="vv_none",
        )

    def fetch_macro_snapshot(
        self,
        series: list[ChoiceMacroSeriesConfig],
        timeout_seconds: float = 10.0,
        request_options: str = "",
    ) -> ChoiceMacroSnapshot:
        client = ChoiceClient()
        client.start()
        effective_options = request_options or f"IsPublishDate=1,RowIndex=1,Ispandas=1,RECVtimeout={int(timeout_seconds)}"
        raw_result = client.edb(
            codes=[item.vendor_series_code for item in series],
            options=effective_options,
        )

        if _is_pandas_dataframe(raw_result):
            raw_payload = _pandas_edb_to_macro_payload(
                frame=raw_result,
                series=series,
            )
        elif isinstance(raw_result, dict):
            raw_payload = raw_result
        else:
            raw_payload = _em_data_to_macro_payload(
                result=raw_result,
                series=series,
            )

        vendor_version = str(raw_payload["vendor_version"])
        points = [
            ChoiceMacroPoint(
                series_id=str(item["series_id"]),
                series_name=str(item["series_name"]),
                vendor_series_code=str(item["vendor_series_code"]),
                vendor_name=self.vendor_name,
                trade_date=str(item["trade_date"]),
                value_numeric=float(item["value_numeric"]),
                frequency=str(item["frequency"]),
                unit=str(item["unit"]),
                vendor_version=vendor_version,
            )
            for item in raw_payload.get("series", [])
        ]

        return ChoiceMacroSnapshot(
            vendor_name=self.vendor_name,
            vendor_version=vendor_version,
            captured_at=str(raw_payload["captured_at"]),
            series=points,
            raw_payload=raw_payload,
        )


def _em_data_to_macro_payload(
    result: object,
    series: list[ChoiceMacroSeriesConfig],
) -> dict[str, object]:
    error_code = int(getattr(result, "ErrorCode", 0))
    if error_code != 0:
        raise RuntimeError(getattr(result, "ErrorMsg", f"Choice edb failed: {error_code}"))

    codes = [str(code) for code in getattr(result, "Codes", [])]
    dates = [_normalize_emquant_date(str(date)) for date in getattr(result, "Dates", [])]
    data = getattr(result, "Data", {})
    if not dates:
        raise RuntimeError("Choice edb returned no dates.")

    config_by_vendor_code = {item.vendor_series_code: item for item in series}
    normalized: list[dict[str, object]] = []
    for vendor_code in codes:
        config = config_by_vendor_code.get(vendor_code)
        if config is None:
            continue
        values = data.get(vendor_code, [])
        first_indicator = values[0] if values else []
        value = first_indicator[-1] if first_indicator else None
        if value is None:
            continue
        normalized.append(
            {
                "series_id": config.series_id,
                "series_name": config.series_name,
                "vendor_series_code": config.vendor_series_code,
                "trade_date": dates[-1],
                "value_numeric": float(value),
                "frequency": config.frequency,
                "unit": config.unit,
            }
        )

    return {
        "vendor_version": f"vv_choice_edb_{dates[-1].replace('-', '')}",
        "captured_at": dates[-1],
        "series": normalized,
    }


def _is_pandas_dataframe(value: object) -> bool:
    return value.__class__.__name__ == "DataFrame"


def _pandas_edb_to_macro_payload(
    frame: object,
    series: list[ChoiceMacroSeriesConfig],
) -> dict[str, object]:
    config_by_vendor_code = {item.vendor_series_code: item for item in series}
    normalized: list[dict[str, object]] = []
    latest_trade_date = ""

    for vendor_code, config in config_by_vendor_code.items():
        rows = frame.loc[[vendor_code]] if vendor_code in frame.index else None
        if rows is None or len(rows) == 0:
            continue
        latest = rows.iloc[-1]
        trade_date = _normalize_emquant_date(str(latest["DATES"]))
        latest_trade_date = max(latest_trade_date, trade_date)
        normalized.append(
            {
                "series_id": config.series_id,
                "series_name": config.series_name,
                "vendor_series_code": config.vendor_series_code,
                "trade_date": trade_date,
                "value_numeric": float(latest["RESULT"]),
                "frequency": config.frequency,
                "unit": config.unit,
            }
        )

    if not normalized or not latest_trade_date:
        raise RuntimeError("Choice edb returned no rows.")

    return {
        "vendor_version": f"vv_choice_edb_{latest_trade_date.replace('-', '')}",
        "captured_at": latest_trade_date,
        "series": normalized,
    }


def _normalize_emquant_date(value: str) -> str:
    return value.replace("/", "-").strip()
