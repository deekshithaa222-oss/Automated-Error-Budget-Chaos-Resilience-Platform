#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class NetemCommand:
    container: str
    args: tuple[str, ...]

    def docker_exec(self) -> list[str]:
        return ["docker", "exec", self.container, *self.args]


def run(command: NetemCommand) -> None:
    print("+", " ".join(command.docker_exec()))
    subprocess.run(command.docker_exec(), check=True)


def clear(container: str) -> None:
    subprocess.run(
        ["docker", "exec", container, "tc", "qdisc", "del", "dev", "eth0", "root"],
        check=False,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Inject deterministic Linux tc/netem faults.")
    sub = parser.add_subparsers(dest="mode", required=True)

    for name in ("delay", "loss", "partition", "clear"):
        mode_parser = sub.add_parser(name)
        mode_parser.add_argument("--container", required=True)

    sub.choices["delay"].add_argument("--delay-ms", type=int, default=250)
    sub.choices["delay"].add_argument("--jitter-ms", type=int, default=75)
    sub.choices["loss"].add_argument("--loss-percent", type=float, default=5.0)

    args = parser.parse_args()
    clear(args.container)

    if args.mode == "clear":
        print(f"cleared netem rules on {args.container}")
        return

    if args.mode == "delay":
        run(
            NetemCommand(
                args.container,
                (
                    "tc",
                    "qdisc",
                    "add",
                    "dev",
                    "eth0",
                    "root",
                    "netem",
                    "delay",
                    f"{args.delay_ms}ms",
                    f"{args.jitter_ms}ms",
                ),
            )
        )
    elif args.mode == "loss":
        run(
            NetemCommand(
                args.container,
                (
                    "tc",
                    "qdisc",
                    "add",
                    "dev",
                    "eth0",
                    "root",
                    "netem",
                    "loss",
                    f"{args.loss_percent}%",
                ),
            )
        )
    elif args.mode == "partition":
        run(
            NetemCommand(
                args.container,
                ("tc", "qdisc", "add", "dev", "eth0", "root", "netem", "loss", "100%"),
            )
        )


if __name__ == "__main__":
    main()

