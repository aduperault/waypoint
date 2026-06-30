import config


def test_validate_config_no_warnings_for_current_valid_settings():
    # As shipped, config.py should currently pass its own sanity checks.
    warnings = config.validate_config()
    assert warnings == []


def test_validate_config_flags_past_registration_deadline(monkeypatch):
    monkeypatch.setattr(config, "REGISTRATION_DEADLINE", "2000-01-01")
    warnings = config.validate_config()
    assert any("in the past" in w for w in warnings)


def test_validate_config_flags_invalid_date_format(monkeypatch):
    monkeypatch.setattr(config, "REGISTRATION_DEADLINE", "not-a-date")
    warnings = config.validate_config()
    assert any("not a valid" in w for w in warnings)


def test_validate_config_flags_non_positive_threshold(monkeypatch):
    monkeypatch.setattr(config, "CREDENTIAL_THRESHOLDS", {"certificate": 0, "associates": 60})
    warnings = config.validate_config()
    assert any("certificate" in w and "positive number" in w for w in warnings)


def test_validate_config_flags_non_numeric_threshold(monkeypatch):
    monkeypatch.setattr(config, "CREDENTIAL_THRESHOLDS", {"certificate": "thirty"})
    warnings = config.validate_config()
    assert any("certificate" in w for w in warnings)
