from __future__ import annotations

import base64
import hashlib
import time
import uuid
from urllib.parse import quote, urlencode

from loguru import logger


class TencentAsrService:
    """Generate signed WebSocket URL for Tencent Cloud real-time ASR."""

    HOST: str = "asr.cloud.tencent.com.cn"
    PATH: str = "/asr/v2/"

    def generate_sign_url(
        self,
        appid: str,
        secret_id: str,
        secret_key: str,
        engine_model_type: str = "16k_zh",
    ) -> str:
        # Strip whitespace to avoid signature mismatch
        appid = appid.strip()
        secret_id = secret_id.strip()
        secret_key = secret_key.strip()

        timestamp = int(time.time())
        expired = timestamp + 86400
        nonce = timestamp
        voice_id = uuid.uuid4().hex

        params = {
            "engine_model_type": engine_model_type,
            "expired": str(expired),
            "needvad": "1",
            "nonce": str(nonce),
            "secretid": secret_id,
            "timestamp": str(timestamp),
            "voice_format": "1",
            "voice_id": voice_id,
            "filter_dirty": "1",
            "filter_modal": "1",
            "filter_punc": "1",
            "convert_num_mode": "1",
            "word_info": "0",
        }

        sorted_params = {key: params[key] for key in sorted(params.keys())}
        query_parts = urlencode(sorted_params)

        sign_original = f"{self.HOST}{self.PATH}{appid}?{query_parts}"

        logger.debug(
            f"Tencent ASR sign original: {self.HOST}{self.PATH}{appid}?engine_model_type={engine_model_type}&...&secretid={secret_id[:6]}***"
        )

        sign_payload = (sign_original + secret_key).encode("utf-8")
        sign_bytes = hashlib.sha1(sign_payload).digest()
        signature = base64.b64encode(sign_bytes).decode("utf-8")

        encoded_signature = quote(signature, safe="")
        wss_url = f"wss://{self.HOST}{self.PATH}{appid}?{query_parts}&signature={encoded_signature}"

        return wss_url
