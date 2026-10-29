#!/usr/bin/env python3
"""Tide: batch Claude Code notifications into one digest per interval.

See CLAUDE.md for the CLI contract and docs/PRD.md for the spec.
Standard library only. Python 3.11+.
"""
from __future__ import annotations

import argparse
import sys


def cmd_hook(args: argparse.Namespace) -> int:
    raise NotImplementedError("hook")


def cmd_flush(args: argparse.Namespace) -> int:
    raise NotImplementedError("flush")


def cmd_status(args: argparse.Namespace) -> int:
    raise NotImplementedError("status")


def cmd_install(args: argparse.Namespace) -> int:
    raise NotImplementedError("install")


def cmd_uninstall(args: argparse.Namespace) -> int:
    raise NotImplementedError("uninstall")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tide", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("hook", help="read one Notification event from stdin").set_defaults(func=cmd_hook)
    sub.add_parser("flush", help="send the digest for everything queued").set_defaults(func=cmd_flush)
    sub.add_parser("now", help="same as flush").set_defaults(func=cmd_flush)
    sub.add_parser("status", help="show what is queued and today's counts").set_defaults(func=cmd_status)
    sub.add_parser("install", help="add the hook and the schedule").set_defaults(func=cmd_install)
    sub.add_parser("uninstall", help="remove the hook and the schedule").set_defaults(func=cmd_uninstall)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
