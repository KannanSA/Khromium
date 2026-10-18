# Copyright 2026 Khromium. All rights reserved.
# Proprietary commercial software. See LICENSE.khromium at the repo root.

"""Idempotent license issuance keyed by Checkout Session id."""

import fcntl
import json
import os
import re
import threading
import time
from pathlib import Path

from khromium_classifier import license_key

from khromium_site.config import PLANS

SESSION_RE = re.compile(r"^cs_[A-Za-z0-9_]{10,200}$")
_PAYABLE_SUBSCRIPTION = {"active", "trialing"}


class IssuanceError(Exception):
    """The session cannot receive a license key."""


class LicenseStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._thread = threading.Lock()

    def _exclusive(self):
        return _FileLock(self)

    def _read(self) -> dict:
        if not self.path.is_file():
            return {"sessions": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise IssuanceError(
                "The issued-license file is unreadable. Refusing to mint a replacement key."
            ) from exc
        sessions = data.get("sessions") if isinstance(data, dict) else None
        if not isinstance(sessions, dict):
            raise IssuanceError(
                "The issued-license file is unreadable. Refusing to mint a replacement key."
            )
        return {"sessions": sessions}

    def _write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(data, indent=2, sort_keys=True) + "\n"
        tmp = self.path.parent / f".{self.path.name}.{os.getpid()}.tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
        except Exception:
            tmp.unlink(missing_ok=True)
            raise
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.path)
        os.chmod(self.path, 0o600)

    def get(self, session_id: str) -> dict | None:
        with self._exclusive():
            row = self._read()["sessions"].get(session_id)
            return dict(row) if isinstance(row, dict) else None

    def put_if_absent(self, session_id: str, builder):
        with self._exclusive():
            data = self._read()
            current = data["sessions"].get(session_id)
            if isinstance(current, dict) and current.get("key"):
                return current
            record = builder()
            if record is None:
                return None
            data["sessions"][session_id] = record
            self._write(data)
            return record


class _FileLock:
    def __init__(self, store: LicenseStore):
        self.store = store
        self.fd = None

    def __enter__(self):
        self.store._thread.acquire()
        self.store.path.parent.mkdir(parents=True, exist_ok=True)
        self.fd = os.open(str(self.store.path) + ".lock", os.O_CREAT | os.O_RDWR, 0o600)
        fcntl.flock(self.fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if self.fd is not None:
                fcntl.flock(self.fd, fcntl.LOCK_UN)
                os.close(self.fd)
        finally:
            self.store._thread.release()
        return False


def mint_checkout_plan(plan: str, subject: str, days: int, now: int) -> str:
    """Mint with the classifier helper.

    Monthly and yearly are the checkout plans. When the helper only accepts
    ``ai_monthly``, that token is used for the same number of paid days so
    ``verify()`` still accepts the key and Shield's AI entitlement matches
    the term. It does not grant the separate browser-purchase entitlement.
    """

    known = set(license_key.PLANS)
    if plan in known:
        return license_key.mint(plan, subject, days=days, now=now)
    if "ai_monthly" in known:
        return license_key.mint("ai_monthly", subject, days=days, now=now)
    raise IssuanceError("The license helper cannot mint this plan.")


def default_licenses_path() -> Path:
    override = os.environ.get("KHROMIUM_ISSUED_LICENSES_PATH", "").strip()
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[1] / "data" / "issued_licenses.json"


def subscription_status(session: dict) -> str:
    subscription = session.get("subscription")
    if isinstance(subscription, dict):
        return str(subscription.get("status") or "").strip().lower()
    return ""


def payment_allows_license(session: dict) -> bool:
    if str(session.get("payment_status") or "") == "paid":
        return True
    return subscription_status(session) in _PAYABLE_SUBSCRIPTION


def customer_email(session: dict) -> str:
    details = session.get("customer_details")
    email = ""
    if isinstance(details, dict):
        email = str(details.get("email") or "")
    if not email.strip():
        email = str(session.get("customer_email") or "")
    return email.strip()


def session_plan(session: dict) -> str:
    metadata = session.get("metadata") if isinstance(session.get("metadata"), dict) else {}
    plan = str(metadata.get("plan") or "").strip().lower()
    if plan not in PLANS:
        raise IssuanceError("Stripe did not return a monthly or yearly plan on this session.")
    return plan


class IssueResult:
    def __init__(self, issued: bool, record: dict | None, reason: str):
        self.issued = issued
        self.record = record
        self.reason = reason


def issue_from_session(session: dict, store: LicenseStore, now: float | None = None) -> IssueResult:
    session_id = str(session.get("id") or "")
    if not SESSION_RE.fullmatch(session_id):
        raise IssuanceError("That Checkout Session id is not valid.")

    def builder():
        if not payment_allows_license(session):
            return None
        email = customer_email(session)
        if not email:
            raise IssuanceError("missing email")
        plan = session_plan(session)
        issued_at = int(now if now is not None else time.time())
        token = mint_checkout_plan(plan, email, PLANS[plan]["days"], issued_at)
        return {
            "key": token,
            "email": email,
            "plan": plan,
            "session_id": session_id,
            "issued_at": issued_at,
        }

    try:
        record = store.put_if_absent(session_id, builder)
    except IssuanceError as exc:
        if str(exc) == "missing email":
            return IssueResult(False, None, "missing_email")
        raise
    if record is None:
        return IssueResult(False, None, "unpaid")
    return IssueResult(True, record, "issued")
