import re

# scheme://user:pass@ 형태 (git push https://user:TOKEN@github.com/... 등)
_CREDENTIALS_RE = re.compile(r"(https?://)[^/\s@]+:[^/\s@]+@")
# 구분자 없이 긴 토큰만 박힌 scheme://TOKEN@ 형태 (git push https://ghp_xxx@github.com/...)
_BARE_TOKEN_RE = re.compile(r"(https?://)[^/\s@:]{20,}@")


def mask_command_summary(text: str) -> str:
    """URL에 박힌 자격증명을 가린다. R03처럼 완벽한 탐지가 목표가 아니라
    눈에 띄는 실수(user:token@ 또는 token@ 형태)만 가리는 수준으로 범위를 좁힌다."""
    text = _CREDENTIALS_RE.sub(r"\1***@", text)
    text = _BARE_TOKEN_RE.sub(r"\1***@", text)
    return text
