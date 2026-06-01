from __future__ import annotations

from typing import Any

from backend.app.config.choice_runtime import AppSettings, _get_em_c, configure_emquant_parent, load_settings


class ChoiceClient:
    def __init__(self, settings: AppSettings | None = None):
        self.settings = settings or load_settings()
        self._started = False

    def start(self) -> Any:
        if self._started:
            return 0
        configure_emquant_parent(self.settings.choice_emquant_parent)
        cmod = _get_em_c()
        if cmod is None:
            raise ImportError("EmQuantAPI.c is unavailable. Configure CHOICE_EMQUANT_PARENT or config/settings.yaml first.")
        result = cmod.start(self.settings.choice_start_options)
        error_code = result.ErrorCode if hasattr(result, "ErrorCode") else 0
        if error_code != 0:
            raise RuntimeError(getattr(result, "ErrorMsg", f"Choice start failed: {error_code}"))
        self._started = True
        return result

    def edb(self, codes: list[str], options: str = "") -> Any:
        self.start()
        cmod = _get_em_c()
        merged = self._merge_request_options(options, include_recv_timeout=True)
        return cmod.edb(codes, merged)

    def edbquery(self, codes: str, options: str = "") -> Any:
        self.start()
        cmod = _get_em_c()
        merged = self._merge_request_options(options, include_recv_timeout=False)
        return cmod.edbquery(codes, merged)

    def cnq(self, codes: str, content: str, options: str = "", callback=None, userparams=None) -> Any:
        self.start()
        cmod = _get_em_c()
        merged = self._merge_request_options(options, include_recv_timeout=True)
        result = cmod.cnq(codes, content, merged, callback, userparams)
        error_code = result.ErrorCode if hasattr(result, "ErrorCode") else 0
        if error_code != 0:
            raise RuntimeError(getattr(result, "ErrorMsg", f"Choice cnq failed: {error_code}"))
        return result

    def cnqcancel(self, serial_id: int) -> Any:
        self.start()
        cmod = _get_em_c()
        result = cmod.cnqcancel(serial_id)
        error_code = result.ErrorCode if hasattr(result, "ErrorCode") else 0
        if error_code != 0:
            raise RuntimeError(getattr(result, "ErrorMsg", f"Choice cnqcancel failed: {error_code}"))
        return result

    def cfn(self, *args: Any, options: str = "") -> Any:
        self.start()
        cmod = _get_em_c()
        merged = self._merge_request_options(options, include_recv_timeout=False)
        return cmod.cfn(*args, merged)

    def cfnquery(self, *args: Any, options: str = "") -> Any:
        self.start()
        cmod = _get_em_c()
        merged = self._merge_request_options(options, include_recv_timeout=False)
        return cmod.cfnquery(*args, merged)

    def tradedates(self, *args: Any, options: str = "") -> Any:
        self.start()
        cmod = _get_em_c()
        merged = self._merge_request_options(options, include_recv_timeout=True)
        return cmod.tradedates(*args, merged)

    def css(self, *args: Any, options: str = "") -> Any:
        self.start()
        cmod = _get_em_c()
        merged = self._merge_request_options(options, include_recv_timeout=True)
        return cmod.css(*args, merged)

    def csd(self, *args: Any, options: str = "") -> Any:
        self.start()
        cmod = _get_em_c()
        merged = self._merge_request_options(options, include_recv_timeout=True)
        return cmod.csd(*args, merged)

    def ctr(self, *args: Any, options: str = "") -> Any:
        self.start()
        cmod = _get_em_c()
        merged = self._merge_request_options(options, include_recv_timeout=False)
        return cmod.ctr(*args, merged)

    def fut_transaction_rankings(self, symbols: str, trade_date: str = "", indicators: str = "volume,long,short") -> Any:
        self.start()
        cmod = _get_em_c()
        fetcher = getattr(cmod, "fut_get_transaction_rankings", None)
        if fetcher is None:
            raise RuntimeError("Choice runtime does not expose fut_get_transaction_rankings.")
        return fetcher(symbols, trade_date, indicators)

    def _merge_request_options(self, options: str, include_recv_timeout: bool) -> str:
        merged = ",".join(
            item.strip()
            for item in [self.settings.choice_request_options, options]
            if item and item.strip()
        )
        if include_recv_timeout:
            return merged
        return ",".join(
            part for part in merged.split(",")
            if part and not part.strip().lower().startswith("recvtimeout=")
        )
