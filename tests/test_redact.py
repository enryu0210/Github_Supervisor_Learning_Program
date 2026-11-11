from gitcoach import redact


def test_masks_user_and_password_credentials() -> None:
    text = "git push https://user:ghp_secrettoken@github.com/team/repo.git main"
    masked = redact.mask_command_summary(text)
    assert "ghp_secrettoken" not in masked
    assert "user" not in masked
    assert masked == "git push https://***@github.com/team/repo.git main"


def test_masks_bare_long_token_without_separator() -> None:
    text = "git push https://ghp_1234567890abcdefxyz@github.com/team/repo.git main"
    masked = redact.mask_command_summary(text)
    assert "ghp_1234567890abcdefxyz" not in masked
    assert masked == "git push https://***@github.com/team/repo.git main"


def test_does_not_touch_plain_url_without_credentials() -> None:
    text = "git push origin main"
    assert redact.mask_command_summary(text) == text

    text_with_url = "git clone https://github.com/team/repo.git"
    assert redact.mask_command_summary(text_with_url) == text_with_url


def test_does_not_mask_short_bare_segment_before_at() -> None:
    # 20자 미만의 짧은 값은 토큰으로 보지 않는다(과탐지 방지)
    text = "git push https://short@github.com/team/repo.git main"
    assert redact.mask_command_summary(text) == text
