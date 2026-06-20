from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import subprocess
from http import cookies
from ipaddress import ip_address
from datetime import datetime, timedelta
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit


ROLE_TITLES = {
    "lead": "Leader",
    "product-manager": "Product Manager",
    "frontend-developer": "Frontend Developer",
    "developer": "Developer",
    "backend-api-contract-engineer": "Backend API Contract Engineer",
    "metric-caliber-officer": "Metric Caliber Officer",
    "data-lineage-auditor": "Data Lineage Auditor",
    "security-permission-auditor": "Security Permission Auditor",
    "asset-liability-manager": "Asset Liability Manager",
    "pnl-attribution-analyst": "PnL Attribution Analyst",
    "risk-manager": "Risk Manager",
    "fixed-income-analyst": "Fixed Income Analyst",
    "market-data-specialist": "Market Data Specialist",
    "valuation-accounting-reconciler": "Valuation Accounting Reconciler",
    "ui-ux-page-closer": "UI UX Page Closer",
    "docs-delivery-manager": "Docs Delivery Manager",
    "code-reviewer": "Code Reviewer",
    "qa": "QA",
}

LEASE_MINUTES = 30
DISPATCH_TOKEN_HEADER = "X-Hermes-Dispatch-Token"
DISPATCH_TOKEN_COOKIE = "hermes_dispatch_token"
SENSITIVE_STATIC_PATHS = {"/manifest.json"}
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
SAFE_STATUS_TASK_FIELDS = {
    "task_id",
    "role",
    "title",
    "sender",
    "created_at",
    "updated_at",
    "state",
    "attempts",
    "last_error",
    "lease_expires_at",
    "heartbeat_at",
    "completed_at",
    "inbox",
    "dispatch_log",
    "workspace",
    "events",
}


class HermesTeamDispatch:
    def __init__(self, team_dir: Path | str) -> None:
        self.team_dir = Path(team_dir).resolve()
        self.manifest_path = self.team_dir / "manifest.json"
        self.queue_path = self.team_dir / "queue" / "tasks.json"
        self.manifest = self._load_manifest()
        self.roles = self._load_roles()
        self.launchers = self._load_launchers()
        self.workspaces = self._load_workspaces()

    def _load_manifest(self) -> dict[str, Any]:
        if not self.manifest_path.exists():
            raise FileNotFoundError(f"manifest.json not found: {self.manifest_path}")
        return json.loads(self.manifest_path.read_text(encoding="utf-8-sig"))

    def _load_roles(self) -> dict[str, str]:
        roles = {}
        for role in self.manifest.get("roles", []):
            slug = str(role.get("slug") or "").strip()
            title = str(
                role.get("display_title") or role.get("title") or ROLE_TITLES.get(slug, slug)
            ).strip()
            if slug:
                roles[slug] = title
        if not roles:
            roles.update(ROLE_TITLES)
        return roles

    def _load_launchers(self) -> dict[str, Path]:
        launchers = {}
        for role in self.manifest.get("roles", []):
            slug = str(role.get("slug") or "").strip()
            launcher = str(role.get("launcher") or "").strip()
            if slug and launcher:
                launchers[slug] = Path(launcher).resolve()
        return launchers

    def _load_workspaces(self) -> dict[str, Path]:
        workspaces = {}
        for role in self.manifest.get("roles", []):
            slug = str(role.get("slug") or "").strip()
            if not slug:
                continue
            workspace = str(role.get("workspace") or "").strip()
            workspaces[slug] = (
                Path(workspace).resolve()
                if workspace
                else (self.team_dir / "workspaces" / slug).resolve()
            )
        for slug in self.roles:
            workspaces.setdefault(slug, (self.team_dir / "workspaces" / slug).resolve())
        return workspaces

    def health(self) -> dict[str, Any]:
        return {
            "ok": True,
            "team_id": str(self.manifest.get("team_id") or self.team_dir.name),
            "roles": list(self.roles.keys()),
        }

    def status(self) -> dict[str, Any]:
        roles = {
            slug: self.role_status(slug=slug, title=title)
            for slug, title in self.roles.items()
        }
        return {
            "ok": True,
            "team_id": str(self.manifest.get("team_id") or self.team_dir.name),
            "roles": roles,
            "interventions": [
                item for role_status in roles.values() for item in role_status["attention"]
            ],
        }

    def role_status(self, *, slug: str, title: str) -> dict[str, Any]:
        inbox_path = self.team_dir / "inbox" / f"{slug}.md"
        outbox_path = self.team_dir / "outbox" / f"{slug}.md"
        session_path = self.team_dir / "sessions" / f"{slug}.txt"
        role_queue = self.tasks_for_role(slug)
        raw_recent_task = role_queue[-1] if role_queue else self.latest_task_from_inbox(inbox_path)
        attention = self.attention_items(role_queue, outbox_path=outbox_path)
        log_tail = ""
        if raw_recent_task and raw_recent_task.get("dispatch_log"):
            try:
                log_tail = self.read_text_inside_team(str(raw_recent_task["dispatch_log"]), limit=6000)
            except ValueError:
                log_tail = ""
        task_state = self.task_state(
            recent_task=raw_recent_task,
            log_path=Path(raw_recent_task["dispatch_log"]) if raw_recent_task and raw_recent_task.get("dispatch_log") else None,
            outbox_path=outbox_path,
            attention=attention,
        )
        return {
            "slug": slug,
            "title": title,
            "session_id": self.read_file_if_exists(session_path).strip(),
            "inbox": str(inbox_path),
            "outbox": str(outbox_path),
            "outbox_updated_at": self.modified_at(outbox_path),
            "outbox_preview": self.read_file_if_exists(outbox_path, limit=6000),
            "workspace": str(self.workspaces[slug]),
            "queue": [self.public_task_view(task) for task in role_queue],
            "queue_count": len(role_queue),
            "attention": attention,
            "recent_task": self.public_task_view(raw_recent_task),
            "log_tail": log_tail,
            "task_state": task_state,
        }

    def public_task_view(self, task: dict[str, Any] | None) -> dict[str, Any] | None:
        if not task:
            return None
        return {key: task[key] for key in SAFE_STATUS_TASK_FIELDS if key in task}

    def task_state(
        self,
        *,
        recent_task: dict[str, Any] | None,
        log_path: Path | None,
        outbox_path: Path,
        attention: list[dict[str, Any]] | None = None,
    ) -> str:
        if not recent_task:
            return "idle"
        if attention:
            return "needs_attention"
        explicit_state = str(recent_task.get("state") or "").strip()
        task_id = str(recent_task.get("task_id") or "").strip()
        if task_id and self.outbox_reports_task_completed(outbox_path, task_id):
            return "completed"
        if explicit_state == "completed":
            return "completed"
        if explicit_state == "failed":
            return "needs_attention"
        if outbox_path.exists() and log_path and log_path.exists():
            if outbox_path.stat().st_mtime >= log_path.stat().st_mtime:
                return "completed"
        if log_path and log_path.exists():
            return "running"
        if outbox_path.exists() and outbox_path.stat().st_size > 0:
            text = self.read_file_if_exists(outbox_path, limit=2000).lower()
            if "no report yet" not in text:
                return "completed"
        return "dispatched"

    def attention_items(
        self,
        tasks: list[dict[str, Any]],
        *,
        outbox_path: Path | None = None,
    ) -> list[dict[str, Any]]:
        items = []
        now = datetime.now()
        for task in tasks:
            reason = ""
            state = str(task.get("state") or "").strip()
            last_error = str(task.get("last_error") or "").strip()
            task_id = str(task.get("task_id") or "").strip()
            if outbox_path and task_id and self.outbox_reports_task_completed(outbox_path, task_id):
                continue
            if state == "failed":
                reason = "runner_failed"
            elif last_error:
                reason = "wake_failed"
            elif state in {"running", "claimed"}:
                process_id = self.process_id_from_task(task)
                if process_id and not self.is_process_running(process_id):
                    reason = "process_exited_without_completion"
                if reason:
                    pass
                else:
                    lease_expires_at = self.parse_timestamp(task.get("lease_expires_at"))
                    if lease_expires_at and lease_expires_at <= now:
                        reason = "lease_expired"
            if reason:
                items.append(
                    {
                        "task_id": task_id,
                        "role": str(task.get("role") or ""),
                        "title": str(task.get("title") or ""),
                        "reason": reason,
                        "state": state,
                        "last_error": last_error,
                        "updated_at": str(task.get("updated_at") or ""),
                    }
                )
        return items

    def process_id_from_task(self, task: dict[str, Any]) -> int | None:
        value = task.get("process_id")
        if not value:
            running_events = [
                event
                for event in task.get("events", [])
                if isinstance(event, dict) and event.get("type") == "running"
            ]
            if running_events:
                message = str(running_events[-1].get("message") or "")
                match = re.search(r"\bpid\s+(?P<pid>\d+)\b", message)
                value = match.group("pid") if match else ""
        try:
            process_id = int(value)
        except (TypeError, ValueError):
            return None
        return process_id if process_id > 0 else None

    def is_process_running(self, process_id: int) -> bool:
        if os.name == "nt":
            completed = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    f"if (Get-Process -Id {process_id} -ErrorAction SilentlyContinue) {{ exit 0 }} else {{ exit 1 }}",
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            return completed.returncode == 0
        try:
            os.kill(process_id, 0)
        except OSError:
            return False
        return True

    def outbox_reports_task_completed(self, outbox_path: Path, task_id: str) -> bool:
        text = self.read_file_if_exists(outbox_path)
        if not text:
            return False
        pattern = rf"^## Task {re.escape(task_id)}(?::[^\n]*)?$"
        match = re.search(pattern, text, re.MULTILINE)
        if not match:
            return False
        tail = text[match.end() :]
        next_match = re.search(r"^## Task \d{8}-\d{6}(?::[^\n]*)?$", tail, re.MULTILINE)
        block = tail[: next_match.start()] if next_match else tail
        status = self.field_from_block(block, "Status").lower()
        return status.startswith("completed")

    def latest_task_from_inbox(self, inbox_path: Path) -> dict[str, str] | None:
        text = self.read_file_if_exists(inbox_path)
        matches = list(
            re.finditer(r"^## Task (?P<id>\d{8}-\d{6}): (?P<title>.+)$", text, re.MULTILINE)
        )
        if not matches:
            return None
        match = matches[-1]
        tail = text[match.end() :]
        next_match = re.search(r"^## Task \d{8}-\d{6}: .+$", tail, re.MULTILINE)
        block = tail[: next_match.start()] if next_match else tail
        created_at = self.field_from_block(block, "created_at")
        sender = self.field_from_block(block, "sender")
        dispatch_log = self.field_from_block(block, "dispatch_log")
        return {
            "task_id": match.group("id"),
            "title": match.group("title").strip(),
            "created_at": created_at,
            "sender": sender,
            "dispatch_log": dispatch_log,
        }

    def field_from_block(self, block: str, field: str) -> str:
        pattern = rf"^{re.escape(field)}:\s*(?P<value>.+)$"
        match = re.search(pattern, block, re.MULTILINE)
        return match.group("value").strip() if match else ""

    def modified_at(self, path: Path) -> str:
        if not path.exists():
            return ""
        return datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")

    def timestamp(self, when: datetime | None = None) -> str:
        return (when or datetime.now()).isoformat(sep=" ", timespec="seconds")

    def lease_expires_at(self, when: datetime | None = None) -> str:
        return self.timestamp((when or datetime.now()) + timedelta(minutes=LEASE_MINUTES))

    def parse_timestamp(self, value: Any) -> datetime | None:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None

    def add_event(
        self,
        task: dict[str, Any],
        event_type: str,
        *,
        when: datetime | None = None,
        message: str = "",
    ) -> None:
        event: dict[str, Any] = {"at": self.timestamp(when), "type": event_type}
        if message:
            event["message"] = message
        events = task.setdefault("events", [])
        if isinstance(events, list):
            events.append(event)
        else:
            task["events"] = [event]

    def claim_task(self, task: dict[str, Any], *, role: str, when: datetime | None = None) -> None:
        now = when or datetime.now()
        task["claimed_by"] = role
        task["claim_token"] = task.get("claim_token") or secrets.token_urlsafe(16)
        task["heartbeat_at"] = self.timestamp(now)
        task["lease_expires_at"] = self.lease_expires_at(now)
        self.add_event(task, "claimed", when=now)

    def task_claim_token(self, task_id: str) -> str:
        task = self.find_task(task_id)
        if not task:
            raise ValueError(f"Unknown task: {task_id}")
        return str(task.get("claim_token") or "")

    def require_task_claim_token(self, task_id: str, supplied_token: str) -> None:
        expected_token = self.task_claim_token(task_id)
        if not expected_token or not secrets.compare_digest(supplied_token, expected_token):
            raise ValueError("invalid task claim token")

    def read_file_if_exists(self, path: Path, limit: int | None = None) -> str:
        if not path.exists():
            return ""
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        if limit and len(text) > limit:
            return text[-limit:]
        return text

    def read_text_inside_team(self, raw_path: str, limit: int | None = 12000) -> str:
        path = Path(raw_path).resolve()
        try:
            path.relative_to(self.team_dir)
        except ValueError as exc:
            raise ValueError("path is outside team directory") from exc
        relative = path.relative_to(self.team_dir)
        if relative.parts[:1] in {("queue",), ("prompts",), ("launch",), ("workspaces",)}:
            raise ValueError("path is not readable through the dashboard API")
        if relative.as_posix() == "manifest.json":
            raise ValueError("path is not readable through the dashboard API")
        return self.read_file_if_exists(path, limit=limit)

    def load_queue(self) -> list[dict[str, Any]]:
        if not self.queue_path.exists():
            return []
        payload = json.loads(self.queue_path.read_text(encoding="utf-8-sig") or "[]")
        if not isinstance(payload, list):
            raise ValueError("queue/tasks.json must contain a JSON array")
        return [task for task in payload if isinstance(task, dict)]

    def save_queue(self, tasks: list[dict[str, Any]]) -> None:
        self.queue_path.parent.mkdir(parents=True, exist_ok=True)
        self.queue_path.write_text(
            json.dumps(tasks, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def tasks_for_role(self, role: str) -> list[dict[str, Any]]:
        return [task for task in self.load_queue() if task.get("role") == role]

    def find_task(self, task_id: str) -> dict[str, Any] | None:
        task_id = task_id.strip()
        for task in self.load_queue():
            if task.get("task_id") == task_id:
                return task
        return None

    def replace_task(self, updated_task: dict[str, Any]) -> None:
        tasks = self.load_queue()
        task_id = updated_task.get("task_id")
        for index, task in enumerate(tasks):
            if task.get("task_id") == task_id:
                tasks[index] = updated_task
                self.save_queue(tasks)
                return
        tasks.append(updated_task)
        self.save_queue(tasks)

    def dispatch_task(
        self,
        *,
        role: str,
        title: str,
        body: str,
        sender: str = "human",
    ) -> dict[str, Any]:
        role = role.strip()
        title = title.strip() or "Untitled task"
        body = body.strip()
        sender = sender.strip() or "human"
        if role not in self.roles:
            raise ValueError(f"Unknown role: {role}")
        if not body:
            raise ValueError("body is required")

        inbox_dir = self.team_dir / "inbox"
        inbox_dir.mkdir(parents=True, exist_ok=True)
        inbox_path = inbox_dir / f"{role}.md"
        existing = ""
        if inbox_path.exists():
            existing = inbox_path.read_text(encoding="utf-8-sig").rstrip()

        now = datetime.now()
        timestamp = self.timestamp(now)
        task_id = f"{now.strftime('%Y%m%d-%H%M%S')}-{now.microsecond:06d}-{secrets.token_hex(3)}"
        log_path = self.log_path_for(role=role, task_id=task_id)
        task_record: dict[str, Any] = {
            "task_id": task_id,
            "role": role,
            "title": title,
            "sender": sender,
            "created_at": timestamp,
            "updated_at": timestamp,
            "state": "queued",
            "attempts": 0,
            "last_error": "",
            "claimed_by": "",
            "claim_token": "",
            "lease_expires_at": "",
            "heartbeat_at": "",
            "completed_at": "",
            "inbox": str(inbox_path),
            "dispatch_log": str(log_path),
            "workspace": str(self.workspaces[role]),
            "events": [{"at": timestamp, "type": "queued"}],
        }
        entry = (
            f"## Task {task_id}: {title}\n\n"
            f"sender: {sender}\n"
            f"assigned_role: {role}\n"
            f"created_at: {timestamp}\n\n"
            f"dispatch_log: {log_path}\n\n"
            f"{body}\n\n"
            "Completion:\n"
            f"- Write results to outbox/{role}.md.\n"
            "- Include verification evidence and blockers.\n"
        )
        content = f"{existing}\n\n{entry}\n" if existing else f"# Inbox: {self.roles[role]}\n\n{entry}\n"
        inbox_path.write_text(content, encoding="utf-8")
        task_record["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        launcher = self.launchers.get(role)
        if launcher and launcher.exists():
            task_record["state"] = "running"
            task_record["attempts"] = 1
            self.claim_task(task_record, role=role)
            tasks = self.load_queue()
            tasks.append(task_record)
            self.save_queue(tasks)
            wake = self.wake_role(
                role=role,
                task_id=task_id,
                log_path=log_path,
                claim_token=str(task_record["claim_token"]),
            )
            if wake.get("ok"):
                self.add_event(task_record, "running", message=f"pid {wake.get('pid')}")
            else:
                task_record["state"] = "queued"
                task_record["last_error"] = str(wake.get("reason") or "wake_failed")
                task_record["claimed_by"] = ""
                task_record["claim_token"] = ""
                task_record["lease_expires_at"] = ""
                task_record["heartbeat_at"] = ""
                self.add_event(task_record, "wake_failed", message=task_record["last_error"])
            self.replace_task(task_record)
        else:
            wake = self.wake_role(role=role, task_id=task_id, log_path=log_path)
            task_record["last_error"] = str(wake.get("reason") or "wake_failed")
            self.add_event(task_record, "wake_failed", message=task_record["last_error"])
            tasks = self.load_queue()
            tasks.append(task_record)
            self.save_queue(tasks)
        return {
            "ok": True,
            "role": role,
            "title": title,
            "inbox": str(inbox_path),
            "task_id": task_id,
            "wake": wake,
        }

    def retry_task(self, task_id: str) -> dict[str, Any]:
        task = self.find_task(task_id)
        if not task:
            raise ValueError(f"Unknown task: {task_id}")
        role = str(task.get("role") or "").strip()
        if role not in self.roles:
            raise ValueError(f"Unknown role: {role}")
        attempts = int(task.get("attempts") or 0) + 1
        log_path = self.log_path_for(role=role, task_id=str(task["task_id"]), attempt=attempts)
        task["attempts"] = attempts
        task["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        task["dispatch_log"] = str(log_path)
        task["workspace"] = str(self.workspaces[role])
        launcher = self.launchers.get(role)
        if launcher and launcher.exists():
            task["state"] = "running"
            task["last_error"] = ""
            task["completed_at"] = ""
            self.claim_task(task, role=role)
            self.replace_task(task)
            wake = self.wake_role(
                role=role,
                task_id=str(task["task_id"]),
                log_path=log_path,
                claim_token=str(task["claim_token"]),
            )
            if wake.get("ok"):
                self.add_event(task, "running", message=f"pid {wake.get('pid')}")
            else:
                task["state"] = "queued"
                task["last_error"] = str(wake.get("reason") or "wake_failed")
                task["claimed_by"] = ""
                task["claim_token"] = ""
                task["lease_expires_at"] = ""
                task["heartbeat_at"] = ""
                self.add_event(task, "wake_failed", message=task["last_error"])
        else:
            wake = self.wake_role(role=role, task_id=str(task["task_id"]), log_path=log_path)
            task["state"] = "queued"
            task["last_error"] = str(wake.get("reason") or "wake_failed")
            task["claimed_by"] = ""
            task["claim_token"] = ""
            task["lease_expires_at"] = ""
            task["heartbeat_at"] = ""
            self.add_event(task, "wake_failed", message=task["last_error"])
        self.replace_task(task)
        return {
            "ok": True,
            "task_id": str(task["task_id"]),
            "role": role,
            "attempts": attempts,
            "wake": wake,
        }

    def record_task_heartbeat(
        self,
        task_id: str,
        *,
        state: str = "running",
        message: str = "",
    ) -> dict[str, Any]:
        task = self.find_task(task_id)
        if not task:
            raise ValueError(f"Unknown task: {task_id}")
        now = datetime.now()
        task["state"] = state.strip() or "running"
        task["updated_at"] = self.timestamp(now)
        task["heartbeat_at"] = self.timestamp(now)
        task["lease_expires_at"] = self.lease_expires_at(now)
        task["claimed_by"] = task.get("claimed_by") or task.get("role") or ""
        task["claim_token"] = task.get("claim_token") or secrets.token_urlsafe(16)
        if message:
            task["last_error"] = message
        self.add_event(task, "heartbeat", when=now, message=message)
        self.replace_task(task)
        return {"ok": True, "task_id": str(task["task_id"]), "state": task["state"]}

    def complete_task(
        self,
        task_id: str,
        *,
        exit_code: int = 0,
        message: str = "",
    ) -> dict[str, Any]:
        task = self.find_task(task_id)
        if not task:
            raise ValueError(f"Unknown task: {task_id}")
        now = datetime.now()
        completed_ok = exit_code == 0
        task["state"] = "completed" if completed_ok else "failed"
        task["updated_at"] = self.timestamp(now)
        task["completed_at"] = self.timestamp(now)
        task["heartbeat_at"] = self.timestamp(now)
        task["lease_expires_at"] = ""
        task["last_error"] = "" if completed_ok else message or f"exit_code_{exit_code}"
        self.add_event(
            task,
            "completed" if completed_ok else "failed",
            when=now,
            message=message or ("" if completed_ok else task["last_error"]),
        )
        self.replace_task(task)
        return {
            "ok": True,
            "task_id": str(task["task_id"]),
            "state": task["state"],
            "exit_code": exit_code,
        }

    def log_path_for(self, *, role: str, task_id: str, attempt: int = 1) -> Path:
        if attempt > 1:
            return self.team_dir / "logs" / f"{role}-{task_id}-attempt{attempt}.log"
        return self.team_dir / "logs" / f"{role}-{task_id}.log"

    def wake_role(
        self,
        *,
        role: str,
        task_id: str,
        log_path: Path,
        claim_token: str = "",
    ) -> dict[str, Any]:
        launcher = self.launchers.get(role)
        if not launcher:
            return {"ok": False, "reason": "launcher_not_configured"}
        if not launcher.exists():
            return {
                "ok": False,
                "reason": "launcher_not_found",
                "launcher": str(launcher),
            }

        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_file = log_path.open("a", encoding="utf-8")
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        process = subprocess.Popen(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(launcher),
                "-AutoTaskId",
                task_id,
                "-TaskClaimToken",
                claim_token,
            ],
            cwd=str(self.team_dir),
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            env=env,
        )
        return {
            "ok": True,
            "pid": process.pid,
            "launcher": str(launcher),
            "log": str(log_path),
        }


def make_handler(dispatch: HermesTeamDispatch, dispatch_token: str | None = None):
    expected_token = str(
        dispatch_token
        or dispatch.manifest.get("dispatch_token")
        or os.environ.get("HERMES_DISPATCH_TOKEN")
        or ""
    ).strip()

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=str(dispatch.team_dir), **kwargs)

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _send_json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _serve_dashboard(self) -> None:
            body = (dispatch.team_dir / "dashboard.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header(
                "Set-Cookie",
                f"{DISPATCH_TOKEN_COOKIE}={expected_token}; Path=/; SameSite=Strict; HttpOnly",
            )
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_forbidden(self, message: str) -> None:
            self._send_json(403, {"ok": False, "error": message})

        def _host_name(self, raw_host: str) -> str:
            host = raw_host.strip().lower()
            if not host:
                return ""
            if host.startswith("["):
                end = host.find("]")
                return host[1:end] if end >= 0 else host
            return host.split(":", 1)[0]

        def _loopback_host(self, raw_host: str | None = None) -> bool:
            host = self._host_name(str(raw_host or self.headers.get("Host") or ""))
            return host in LOOPBACK_HOSTS

        def _client_is_loopback(self) -> bool:
            try:
                return ip_address(str(self.client_address[0])).is_loopback
            except ValueError:
                return False

        def _same_origin_request(self) -> bool:
            origin = str(self.headers.get("Origin") or "").strip()
            if not origin:
                return True
            host = str(self.headers.get("Host") or "").strip()
            parsed_origin = urlsplit(origin)
            return (
                parsed_origin.scheme == "http"
                and self._loopback_host(parsed_origin.netloc)
                and self._loopback_host(host)
                and parsed_origin.netloc.lower() == host.lower()
            )

        def _supplied_dispatch_token(self) -> str:
            header_token = str(self.headers.get(DISPATCH_TOKEN_HEADER) or "")
            if header_token:
                return header_token
            raw_cookie = str(self.headers.get("Cookie") or "")
            if not raw_cookie:
                return ""
            cookie = cookies.SimpleCookie()
            try:
                cookie.load(raw_cookie)
            except cookies.CookieError:
                return ""
            morsel = cookie.get(DISPATCH_TOKEN_COOKIE)
            return morsel.value if morsel else ""

        def _api_authorized(self) -> bool:
            if not expected_token:
                self._send_json(
                    503,
                    {
                        "ok": False,
                        "error": "dispatch token is not configured; regenerate the team dashboard",
                    },
                )
                return False
            if not self._client_is_loopback():
                self._send_forbidden("client must connect from loopback")
                return False
            if not self._loopback_host():
                self._send_forbidden("API host must be loopback")
                return False
            if not self._same_origin_request():
                self._send_forbidden("cross-origin API access is not allowed")
                return False
            supplied_token = self._supplied_dispatch_token()
            if not secrets.compare_digest(supplied_token, expected_token):
                self._send_forbidden("invalid dispatch token")
                return False
            return True

        def do_OPTIONS(self) -> None:
            self._send_json(403, {"ok": False, "error": "CORS preflight is not supported"})

        def do_GET(self) -> None:
            path = unquote(self.path.split("?", 1)[0]).rstrip("/")
            if not self._client_is_loopback():
                self._send_forbidden("client must connect from loopback")
                return
            if not self._loopback_host():
                self._send_forbidden("HTTP host must be loopback")
                return
            if path == "/health":
                self._send_json(200, dispatch.health())
                return
            if path in SENSITIVE_STATIC_PATHS:
                self._send_forbidden("static access to this file is not allowed")
                return
            if path == "/api/status":
                if not self._api_authorized():
                    return
                self._send_json(200, dispatch.status())
                return
            if path == "/api/log":
                if not self._api_authorized():
                    return
                query = self.path.split("?", 1)[1] if "?" in self.path else ""
                raw_path = parse_qs(query).get("path", [""])[0]
                try:
                    text = dispatch.read_text_inside_team(raw_path)
                except ValueError as exc:
                    self._send_json(403, {"ok": False, "error": str(exc)})
                    return
                self._send_json(200, {"ok": True, "text": text})
                return
            if path in {"", "/"}:
                self._serve_dashboard()
                return
            if path == "/dashboard.html":
                self._serve_dashboard()
                return
            self._send_json(404, {"ok": False, "error": "not found"})

        def do_POST(self) -> None:
            path = unquote(self.path.split("?", 1)[0]).rstrip("/")
            if path not in {
                "/api/dispatch",
                "/api/retry",
                "/api/task/heartbeat",
                "/api/task/complete",
            }:
                self._send_json(404, {"ok": False, "error": "not found"})
                return
            if not self._api_authorized():
                return
            try:
                length = int(self.headers.get("Content-Length") or "0")
                raw_body = self.rfile.read(length).decode("utf-8")
                payload = json.loads(raw_body or "{}")
                if path == "/api/retry":
                    result = dispatch.retry_task(task_id=str(payload.get("task_id") or ""))
                elif path == "/api/task/heartbeat":
                    task_id = str(payload.get("task_id") or "")
                    dispatch.require_task_claim_token(
                        task_id,
                        str(payload.get("claim_token") or ""),
                    )
                    result = dispatch.record_task_heartbeat(
                        task_id=task_id,
                        state=str(payload.get("state") or "running"),
                        message=str(payload.get("message") or ""),
                    )
                elif path == "/api/task/complete":
                    task_id = str(payload.get("task_id") or "")
                    dispatch.require_task_claim_token(
                        task_id,
                        str(payload.get("claim_token") or ""),
                    )
                    result = dispatch.complete_task(
                        task_id=task_id,
                        exit_code=int(payload.get("exit_code") or 0),
                        message=str(payload.get("message") or ""),
                    )
                else:
                    result = dispatch.dispatch_task(
                        role=str(payload.get("role") or ""),
                        title=str(payload.get("title") or ""),
                        body=str(payload.get("body") or ""),
                        sender=str(payload.get("sender") or "dashboard"),
                    )
                self._send_json(200, result)
            except ValueError as exc:
                self._send_json(400, {"ok": False, "error": str(exc)})
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})

    return Handler


def require_loopback_bind(host: str) -> None:
    raw_host = str(host or "").strip()
    if raw_host == "localhost":
        return
    try:
        if ip_address(raw_host).is_loopback:
            return
    except ValueError:
        pass
    raise SystemExit("Hermes dispatch server must bind to loopback only.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--team-dir", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8795)
    parser.add_argument("--token", default="")
    args = parser.parse_args()

    dispatch = HermesTeamDispatch(args.team_dir)
    dispatch_token = str(
        args.token
        or dispatch.manifest.get("dispatch_token")
        or os.environ.get("HERMES_DISPATCH_TOKEN")
        or ""
    ).strip()
    if not dispatch_token:
        raise SystemExit("Dispatch token not configured; regenerate the team with start-hermes-agent-team.ps1.")
    require_loopback_bind(args.host)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(dispatch, dispatch_token))
    print(f"Hermes team dispatch server: http://{args.host}:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
