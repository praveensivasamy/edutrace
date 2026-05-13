import base64
import hashlib
import hmac
import json
import logging
import re
import secrets
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.student import Student

logger = logging.getLogger(__name__)

KEY_VERSION = 1
ALIAS_PATTERN = re.compile(r"^Student \d{4}$")
SQLITE_HEADER = b"SQLite format 3\x00"

_revealed_names: dict[str, str] = {}
_real_to_alias: dict[str, str] = {}


class PrivacyService:
    def __init__(self, db: Session):
        self.db = db

    def status(self) -> dict[str, Any]:
        students = self.db.scalars(select(Student)).all()
        anonymized_count = sum(
            1 for student in students if self.is_alias(student.student_name)
        )
        return {
            "privacy_enabled": get_settings().privacy_enabled,
            "student_count": len(students),
            "anonymized_count": anonymized_count,
            "reveal_key_loaded": bool(_revealed_names),
            "revealed_count": len(_revealed_names),
        }

    @staticmethod
    def current_database_path() -> str | None:
        settings = get_settings()
        prefix = "sqlite:///"
        if not settings.database_url.startswith(prefix):
            return None
        return settings.database_url.removeprefix(prefix)

    @staticmethod
    def privacy_enabled() -> bool:
        return get_settings().privacy_enabled

    def anonymize_students(self, passphrase: str) -> bytes:
        self._require_passphrase(passphrase)
        students = self.db.scalars(select(Student).order_by(Student.id)).all()
        mapping = {}
        for index, student in enumerate(students, start=1):
            alias = f"Student {index:04d}"
            mapping[alias] = student.student_name
            student.student_name = alias
        self.db.commit()
        encrypted = self.encrypt_mapping(mapping, passphrase)
        clear_reveal_key()
        logger.warning("student_names_anonymized count=%s", len(mapping))
        return encrypted

    @staticmethod
    def display_name(student_name: str) -> str:
        return _revealed_names.get(student_name, student_name)

    @staticmethod
    def storage_name(student_name: str) -> str:
        return _real_to_alias.get(student_name, student_name)

    def require_key_for_anonymized_upload(self) -> None:
        if not self.privacy_enabled():
            return
        status = self.status()
        if status["anonymized_count"] and not _real_to_alias:
            raise ValueError("Load the private student key before approving new uploads.")

    @staticmethod
    def load_reveal_key(content: bytes, passphrase: str) -> int:
        mapping = PrivacyService.decrypt_mapping(content, passphrase)
        _revealed_names.clear()
        _revealed_names.update(mapping)
        _real_to_alias.clear()
        _real_to_alias.update({real_name: alias for alias, real_name in mapping.items()})
        logger.info("student_reveal_key_loaded count=%s", len(mapping))
        return len(mapping)

    @staticmethod
    def rotate_key(new_passphrase: str) -> bytes:
        if not _revealed_names:
            raise ValueError("Load the current key before rotating it.")
        encrypted = PrivacyService.encrypt_mapping(_revealed_names, new_passphrase)
        logger.warning("student_reveal_key_rotated count=%s", len(_revealed_names))
        return encrypted

    @staticmethod
    def restore_database(content: bytes, filename: str | None = None) -> None:
        if not content.startswith(SQLITE_HEADER):
            raise ValueError("Upload a valid SQLite database backup file.")
        target = PrivacyService.current_database_path()
        if not target:
            raise ValueError("Database restore is only supported for file-based SQLite.")
        target_path = Path(target)

        settings = get_settings()
        restore_dir = settings.private_dir / "restores"
        restore_dir.mkdir(parents=True, exist_ok=True)
        temp_path = restore_dir / "restore-upload.tmp"
        temp_path.write_bytes(content)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path.replace(target_path)
        clear_reveal_key()
        logger.warning(
            "database_restored filename=%s target=%s",
            filename or "unknown",
            target_path,
        )

    @staticmethod
    def encrypt_mapping(mapping: dict[str, str], passphrase: str) -> bytes:
        payload = json.dumps(mapping, sort_keys=True).encode("utf-8")
        salt = secrets.token_bytes(16)
        nonce = secrets.token_bytes(16)
        key = PrivacyService._derive_key(passphrase, salt)
        ciphertext = PrivacyService._xor_stream(payload, key, nonce)
        header = {
            "version": KEY_VERSION,
            "salt": base64.b64encode(salt).decode("ascii"),
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
        }
        tag = hmac.new(
            key,
            json.dumps(header, sort_keys=True).encode("utf-8"),
            hashlib.sha256,
        ).digest()
        header["tag"] = base64.b64encode(tag).decode("ascii")
        return json.dumps(header, sort_keys=True, indent=2).encode("utf-8")

    @staticmethod
    def decrypt_mapping(content: bytes, passphrase: str) -> dict[str, str]:
        PrivacyService._require_passphrase(passphrase)
        data = json.loads(content.decode("utf-8"))
        if data.get("version") != KEY_VERSION:
            raise ValueError("Unsupported key file version.")
        salt = base64.b64decode(data["salt"])
        nonce = base64.b64decode(data["nonce"])
        ciphertext = base64.b64decode(data["ciphertext"])
        expected_tag = base64.b64decode(data["tag"])
        key = PrivacyService._derive_key(passphrase, salt)
        signed = {k: data[k] for k in ("ciphertext", "nonce", "salt", "version")}
        actual_tag = hmac.new(
            key,
            json.dumps(signed, sort_keys=True).encode("utf-8"),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(actual_tag, expected_tag):
            raise ValueError("Invalid passphrase or key file.")
        plaintext = PrivacyService._xor_stream(ciphertext, key, nonce)
        mapping = json.loads(plaintext.decode("utf-8"))
        if not isinstance(mapping, dict):
            raise ValueError("Invalid key file mapping.")
        return {str(alias): str(name) for alias, name in mapping.items()}

    @staticmethod
    def is_alias(student_name: str) -> bool:
        return bool(ALIAS_PATTERN.match(student_name))

    @staticmethod
    def _derive_key(passphrase: str, salt: bytes) -> bytes:
        PrivacyService._require_passphrase(passphrase)
        return hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, 200_000, dklen=32)

    @staticmethod
    def _xor_stream(data: bytes, key: bytes, nonce: bytes) -> bytes:
        output = bytearray()
        counter = 0
        while len(output) < len(data):
            block = hmac.new(key, nonce + counter.to_bytes(8, "big"), hashlib.sha256).digest()
            output.extend(block)
            counter += 1
        return bytes(value ^ mask for value, mask in zip(data, output, strict=False))

    @staticmethod
    def _require_passphrase(passphrase: str) -> None:
        if not passphrase or len(passphrase) < 8:
            raise ValueError("Passphrase must be at least 8 characters.")


def clear_reveal_key() -> None:
    _revealed_names.clear()
    _real_to_alias.clear()
    logger.info("student_reveal_key_cleared")
