You can use:

`Producer`:

```shell
uv run python 03.routing/emit.py info "Hello world from Python"
```

`Consumer`:

```shell
uv run python -u 03.routing/receive.py error > 03.routing/out.log
```

```shell
uv run python -u 03.routing/receive.py info warn error
```