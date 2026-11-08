from gitcoach import parser


def test_parse_push_with_remote_and_refspec() -> None:
    cmd = parser.parse(["push", "origin", "main"])
    assert cmd.subcommand == "push"
    assert cmd.remote == "origin"
    assert cmd.refspec == "main"
    assert cmd.flags == []


def test_parse_push_force_flag() -> None:
    cmd = parser.parse(["push", "--force", "origin", "main"])
    assert cmd.flags == ["--force"]
    assert cmd.remote == "origin"
    assert cmd.refspec == "main"


def test_parse_push_no_args() -> None:
    cmd = parser.parse(["push"])
    assert cmd.subcommand == "push"
    assert cmd.remote is None
    assert cmd.refspec is None


def test_parse_commit_message() -> None:
    cmd = parser.parse(["commit", "-m", "fix: 버그 수정"])
    assert cmd.subcommand == "commit"
    assert cmd.message == "fix: 버그 수정"


def test_parse_unknown_subcommand_passes_through() -> None:
    cmd = parser.parse(["status"])
    assert cmd.subcommand == "status"
    assert cmd.remote is None
    assert cmd.message is None


def test_parse_empty_argv() -> None:
    cmd = parser.parse([])
    assert cmd.subcommand == ""
