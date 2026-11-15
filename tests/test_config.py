"""Configuration must never silently change the intended investment universe."""
from pathlib import Path
import pytest
import yaml
from iran_quant.config import load_config


def test_production_defaults_are_real_data():
    settings = load_config(Path(__file__).resolve().parents[1] / 'config' / 'strategy.yml')
    assert settings.mode == 'live'
    assert settings.gold_id == 'GOLD'
    assert settings.defensive_id == 'DEFENSIVE'
    assert set(settings.equity_ids) == {'FOOLAD', 'FMLI', 'WBMLT', 'SHPNA'}


def test_invalid_total_sleeve_is_rejected(tmp_path):
    source = Path(__file__).resolve().parents[1] / 'config' / 'strategy.yml'
    raw = yaml.safe_load(source.read_text(encoding='utf8'))
    raw['strategy']['gold_sleeve'] = 0.8
    file = tmp_path / 'strategy.yml'
    file.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding='utf8')
    with pytest.raises(ValueError, match='Investment sleeves'):
        load_config(file)
