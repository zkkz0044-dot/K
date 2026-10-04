# FKP07 — Persistent Connector Broker

## Proven path
`VPS queue -> ChatGPT connector executor -> minimal receipt -> VPS verifier -> one-time archive`

## Security model
- OAuth/provider credentials remain in ChatGPT connectors; never copied to VPS.
- VPS stores only strict connector requests and minimized verified receipts.
- Queue files are mode 0600 under `/root/K/FK/connector_broker`.
- `github.read` accepts repository metadata lookup only.
- `gmail.search` accepts a bounded query and limit 1..5 only.
- Gmail receipts omit sender/recipient addresses, labels, body, raw MIME, URLs and connector metadata.
- Invalid receipts are rejected before result creation; consumed requests/results are archived once.

## Runtime modes
- Foreground: current ChatGPT session services a queued request immediately when instructed/active.
- Background fallback: may be serviced by a scheduled ChatGPT task, no faster than hourly.
- No claim is made that plain VPS can invoke ChatGPT connectors without a ChatGPT execution context.
