from app.cli import main


def test_run_em_replay_sem_nenhuma_chave(monkeypatch, capsys):
    for key in ("TYPESAFE_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("PROVIDER_MODE", "replay")

    code = main(["run", "--limit", "3", "--no-latency"])

    out = capsys.readouterr().out
    assert code == 0
    assert "tk-0001" in out and "tk-0002" in out and "adv-001" in out
    assert "blocked" in out


def test_run_de_um_ticket(monkeypatch, capsys):
    monkeypatch.setenv("PROVIDER_MODE", "replay")

    assert main(["run", "--ticket", "adv-001", "--no-latency"]) == 0
    assert "adv-001" in capsys.readouterr().out


def test_ticket_sem_gravacao_em_replay_falha(monkeypatch, capsys):
    monkeypatch.setenv("PROVIDER_MODE", "replay")

    assert main(["run", "--ticket", "tk-0300", "--no-latency"]) != 0
    assert "tk-0300" in capsys.readouterr().err


def test_record_exige_modo_live_e_chaves(monkeypatch, capsys):
    monkeypatch.setenv("PROVIDER_MODE", "replay")
    assert main(["record", "--limit", "1"]) != 0

    monkeypatch.setenv("PROVIDER_MODE", "live")
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    assert main(["record", "--limit", "1"]) != 0
    assert "TYPESAFE_API_KEY" in capsys.readouterr().err
