# ciphercache

**ciphercache** is a locally running **secret agent daemon** that unlocks
secrets from a secure store (initially: a KeePassXC database) **once per session** and then serves secrets from an **in-memory cache** without reopening the store. 

Client software can be restarted frequently during development and still retrieve secrets as long as a **session ticket** and **TTL (Time To Live)** remain valid. The primary transport is **IPC (Inter-Process Communication)** via **Unix domain sockets**. 

Optionally, we might later add a **TCP listener with mTLS (mutual TLS, i.e., TLS with client certificate authentication)**.

## Example quickstart

```bash
uv run python main.py
```

## Example tests

```bash
uv run pytest
```

## Project layout

- `src/` application sources
- `tests/` pytest tests
- `spec/` feature specifications
- `data/` data files
- `testdata/` test data
- `doc/` documentation

## PyCharm run configurations

If you use PyCharm, you can add shared run configurations under `.idea/runConfigurations/`.


## License
This project is licensed under the Apache License 2.0. See `LICENSE`.

The software is provided "AS IS", without warranties, guarantees, or conditions of any kind. Use is at your own risk.

## Development note

AI tools were used to assist development.