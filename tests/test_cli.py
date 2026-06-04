from click.testing import CliRunner
from scripts.cli import cli


def test_cli_stats():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["stats"])
        assert result.exit_code == 0
        assert "文章" in result.output


def test_cli_collect_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["collect", "--help"])
    assert result.exit_code == 0
    assert "keyword" in result.output.lower() or "KEYWORD" in result.output
