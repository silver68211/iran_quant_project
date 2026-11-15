"""Full offline integration test; a live quote endpoint is NOT required."""
import json
from iran_quant.pipeline import execute


def test_end_to_end_generates_outputs(settings, tmp_path):
    destination = tmp_path / 'outputs'
    execute(settings, tmp_path, destination)
    for filename in [
        'daily_performance.csv', 'daily_holdings.csv', 'monthly_decisions.csv',
        'trades.csv', 'data_quality.csv', 'performance_metrics.csv',
        'last_target_weights.csv', 'performance_and_drawdowns.png',
        'run_manifest.json', 'RESEARCH_REPORT.md',
    ]:
        assert (destination / filename).is_file(), filename
    provenance = json.loads((destination / 'run_manifest.json').read_text())
    assert provenance['mode'] == 'SYNTHETIC_DEMO_NO_MARKET_DATA'
