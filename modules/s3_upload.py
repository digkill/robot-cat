# -*- coding: utf-8 -*-
"""Загрузка файлов в S3 (Beget)."""

import os
from pathlib import Path
from datetime import datetime

try:
    import boto3
    from botocore.config import Config
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

from config import (
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY,
    AWS_BUCKET,
    AWS_ENDPOINT,
    AWS_USE_PATH_STYLE,
    AWS_DEFAULT_REGION,
)


def upload_file(local_path: str | Path, s3_key: str = None) -> str | None:
    """Загружает файл в S3. Возвращает s3 ключ или None при ошибке."""
    if not HAS_BOTO:
        try:
            from modules.watchlog import log
            log("s3", "boto3 не установлен: pip install boto3")
        except Exception:
            pass
        return None
    if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY or not AWS_BUCKET:
        try:
            from modules.watchlog import log
            log("s3", "не заданы ключи AWS")
        except Exception:
            pass
        return None

    local_path = Path(local_path)
    if not local_path.exists():
        try:
            from modules.watchlog import log
            log("s3", f"файл не найден: {local_path}")
        except Exception:
            pass
        return None

    if s3_key is None:
        ts = datetime.now().strftime("%Y/%m/%d/%H%M%S")
        s3_key = f"recordings/{ts}_{local_path.name}"

    try:
        session = boto3.Session(
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_DEFAULT_REGION,
        )
        client = session.client(
            "s3",
            endpoint_url=AWS_ENDPOINT,
            config=Config(s3={"addressing_style": "path" if AWS_USE_PATH_STYLE else "auto"}),
        )
        client.upload_file(str(local_path), AWS_BUCKET, s3_key)
        try:
            from modules.watchlog import log
            log("s3_upload", s3_key)
        except Exception:
            pass
        return s3_key
    except Exception as e:
        try:
            from modules.watchlog import log
            log("s3", f"ошибка загрузки: {e}")
        except Exception:
            pass
        return None
