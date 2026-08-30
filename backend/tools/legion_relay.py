#!/usr/bin/env python3
"""Relays TCP connections arriving on the docker bridge gateway IP to loopback ports
that a reverse SSH tunnel from the Legion has bound on this host. Needs no root: any
unprivileged user can bind an already-configured local IP on a port >= 1024.

The gateway IP (e.g. 172.21.0.1) is private to the ghostagent_default docker network
and has no route from the public internet, so this does not expose anything externally
- only containers on that network, and other local processes, can reach it.
"""

import argparse
import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("relay")


async def pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while chunk := await reader.read(65536):
            writer.write(chunk)
            await writer.drain()
    except (ConnectionResetError, BrokenPipeError):
        pass
    finally:
        writer.close()


async def handle(
    local_reader: asyncio.StreamReader,
    local_writer: asyncio.StreamWriter,
    target_host: str,
    target_port: int,
) -> None:
    peer = local_writer.get_extra_info("peername")
    try:
        remote_reader, remote_writer = await asyncio.open_connection(target_host, target_port)
    except OSError as exc:
        log.warning("cannot reach %s:%s for %s: %s", target_host, target_port, peer, exc)
        local_writer.close()
        return
    log.info("relaying %s -> %s:%s", peer, target_host, target_port)
    await asyncio.gather(
        pipe(local_reader, remote_writer),
        pipe(remote_reader, local_writer),
    )


async def serve(bind_host: str, bind_port: int, target_host: str, target_port: int) -> None:
    server = await asyncio.start_server(
        lambda r, w: handle(r, w, target_host, target_port), bind_host, bind_port
    )
    log.info("listening on %s:%s -> %s:%s", bind_host, bind_port, target_host, target_port)
    async with server:
        await server.serve_forever()


async def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--bind-host", required=True)
    p.add_argument("--map", action="append", required=True, help="bindport:targethost:targetport")
    args = p.parse_args()
    tasks = []
    for mapping in args.map:
        bind_port, target_host, target_port = mapping.split(":")
        tasks.append(serve(args.bind_host, int(bind_port), target_host, int(target_port)))
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
