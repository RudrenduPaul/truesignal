# Python examples

Each numbered subdirectory is a real, runnable script against the actual
`truesignal` Python library (`from truesignal import ALL_CONNECTORS, ...`),
not pseudocode. `01` and `02` call the two zero-configuration connectors
(`cisa-kev`, `gdelt`) against their real live upstream APIs -- no
credentials or network mocking required, though a working internet
connection is. `03` demonstrates the fully in-process, agent-native call
pattern and JSON serialization.

Install the package first (editable install from this checkout, or `pip
install truesignal` from PyPI both work identically):

```bash
cd python
pip install -e .
```

Then run any example directly:

```bash
python3 examples/01-init-and-feed/run.py
python3 examples/02-ci-gate/gate.py
python3 examples/03-agent-native-json/agent_report.py
```

| Example                                         | What it demonstrates                                                                                                                                                                           |
| ----------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [01-init-and-feed](./01-init-and-feed/)         | The core library call: checking `is_configured()` across `ALL_CONNECTORS`, then pulling a real live feed from the zero-config `cisa-kev` connector.                                            |
| [02-ci-gate](./02-ci-gate/)                     | Using `fetch_items()` as a CI gate: pulls the real live `gdelt` feed and exits non-zero if the fetch produced neither live nor fallback data -- suitable to drop into a CI script directly.    |
| [03-agent-native-json](./03-agent-native-json/) | The agent-native use case: calling TrueSignal in-process (no CLI subprocess), serializing structured `FeedItem`s to JSON, and using `run_verify()` to re-confirm a specific item's provenance. |
