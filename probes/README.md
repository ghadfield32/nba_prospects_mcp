# Data Source Probes

Lightweight validation scripts for CI/CD that test live data source access.

## Purpose
- **Quick validation**: Single API call per league/dataset (~5-10 seconds per probe)
- **CI integration**: Run nightly to catch API changes/outages
- **Guardrail for new leagues**: Probe before implementation

## Usage

```bash
# Run single probe
python probes/probe_wnba.py

# Run all probes
python probes/run_all_probes.py

# Add to CI (GitHub Actions)
# See: .github/workflows/nightly-probes.yml
```

## Probe Structure

Each probe tests 1 known game/endpoint:
1. Makes single API request
2. Validates response structure
3. Checks for expected data (at least 1 row)
4. Returns exit code 0 (success) or 1 (failure)

## Adding New Probes

1. Copy `probe_template.py`
2. Update league/endpoint details
3. Test manually: `python probes/probe_<league>.py`
4. Add to `run_all_probes.py`

## Current Probes

- ✅ `probe_wnba.py` - WNBA schedule/box score
- ✅ `probe_gleague.py` - G-League schedule
- ✅ `probe_eurocup.py` - EuroCup schedule
- 🔄 TODO: CEBL, OTE, U-SPORTS, CCAA

## Exit Codes

- `0` - Success (data accessible, structure valid)
- `1` - Failure (API error, no data, or structure mismatch)
- `2` - Timeout (API took >30s to respond)
