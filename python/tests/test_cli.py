"""End-to-end CLI tests, one pytest module per src/truesignal/cli.ts's subcommands. Exercises
run_cli() directly (no subprocess) for fast, in-process end-to-end coverage."""
import json

from truesignal.cli import run_cli


def test_init_reports_ready_zero_config_connectors_and_exits_0(capsys, cache_dir):
    exit_code = run_cli(["truesignal", "init"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "cisa-kev" in out
    assert "gdelt" in out
    assert "connectors ready." in out


def test_init_json_output_is_valid_and_lists_every_connector(capsys, cache_dir):
    exit_code = run_cli(["truesignal", "init", "--json"])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    names = {c["name"] for c in payload["connectors"]}
    assert names == {"cisa-kev", "cloudflare-radar", "reddit", "telegram", "gdelt"}


def test_feed_with_source_pulls_only_that_connector(monkeypatch, capsys, cache_dir):
    monkeypatch.setattr(
        "truesignal.connectors.cisa_kev.get_json",
        lambda url: {
            "vulnerabilities": [
                {
                    "cveID": "CVE-2026-00001",
                    "vendorProject": "Acme",
                    "product": "Widget",
                    "vulnerabilityName": "Sample RCE",
                    "dateAdded": "2026-01-01",
                    "shortDescription": "desc",
                }
            ]
        },
    )
    exit_code = run_cli(["truesignal", "feed", "--source", "cisa-kev"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "[live]" in out
    assert "CVE-2026-00001" in out


def test_feed_json_output_matches_the_documented_shape(monkeypatch, capsys, cache_dir):
    monkeypatch.setattr(
        "truesignal.connectors.cisa_kev.get_json",
        lambda url: {
            "vulnerabilities": [
                {
                    "cveID": "CVE-2026-00002",
                    "vendorProject": "Acme",
                    "product": "Widget",
                    "vulnerabilityName": "Sample RCE",
                    "dateAdded": "2026-01-01",
                    "shortDescription": "desc",
                }
            ]
        },
    )
    exit_code = run_cli(["truesignal", "feed", "--source", "cisa-kev", "--json"])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    [item] = payload["items"]
    assert item["id"] == "cisa-kev:CVE-2026-00002"
    assert item["status"] == "live"
    assert item["url"].startswith("https://")


def test_feed_with_an_unknown_source_exits_1_and_lists_known_sources(capsys, cache_dir):
    exit_code = run_cli(["truesignal", "feed", "--source", "not-a-real-source"])
    assert exit_code == 1
    err = capsys.readouterr().err
    assert "Unknown source" in err
    assert "cisa-kev" in err


def test_feed_naming_an_unconfigured_connector_exits_2_no_connectors_configured(monkeypatch, capsys, cache_dir):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    exit_code = run_cli(["truesignal", "feed", "--source", "telegram"])
    assert exit_code == 2
    err = capsys.readouterr().err
    assert "No connectors are configured to run" in err


def test_verify_with_a_malformed_item_id_exits_4(capsys, cache_dir):
    exit_code = run_cli(["truesignal", "verify", "not-valid"])
    assert exit_code == 4


def test_verify_with_an_unknown_source_exits_4(capsys, cache_dir):
    exit_code = run_cli(["truesignal", "verify", "not-a-real-source:123"])
    assert exit_code == 4
    err = capsys.readouterr().err
    assert "Unknown source" in err


def test_verify_a_live_item_reports_live_provenance_and_exits_0(monkeypatch, capsys, cache_dir):
    monkeypatch.setattr(
        "truesignal.connectors.cisa_kev.get_json",
        lambda url: {
            "vulnerabilities": [
                {
                    "cveID": "CVE-2026-00003",
                    "vendorProject": "Acme",
                    "product": "Widget",
                    "vulnerabilityName": "Sample RCE",
                    "dateAdded": "2026-01-01",
                    "shortDescription": "desc",
                }
            ]
        },
    )
    exit_code = run_cli(["truesignal", "verify", "cisa-kev:CVE-2026-00003"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "LIVE" in out
    assert "https://nvd.nist.gov/vuln/detail/CVE-2026-00003" in out


def test_verify_naming_an_unconfigured_connector_exits_2(capsys, cache_dir):
    exit_code = run_cli(["truesignal", "verify", "telegram:1:1"])
    assert exit_code == 2


def test_no_command_prints_help_and_exits_0(capsys, cache_dir):
    exit_code = run_cli(["truesignal"])
    assert exit_code == 0
    assert "truesignal" in capsys.readouterr().out
