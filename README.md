# IEX to NICE WFM parser

This small converter consumes the text report in `upload/sample.iex` and writes a NICE WFM Import History XML report.

The IEX sample has six numeric call-group fields after `PILOT`; the source header repeats `DELAY`. The parser treats them, in order, as `ANSWER`, `ABAND`, `ANS`, `ABAN`, `DELAY`, and `TALK`. The resulting mapping is:

- `ContactsReceived` = `ANSWER + ABAND`
- `AbandonedLong` = `ABAND`
- `HandledShort` = `ANS`
- `AbandonedShort` = `ABAN`
- `HandleTime` = `TALK`
- `QueueDelayTime` = `DELAY`

Agent detail values map to `AgentQueueData`; `READY_SEC` is also emitted in `AgentSystemData`. The converter intentionally omits the production `DOCTYPE`, as required by the NICE guide.

## Run

```bash
python3 iex_to_nice.py upload/sample.iex -o output/sample.xml
```

## Test

```bash
python3 -m pytest -q
```