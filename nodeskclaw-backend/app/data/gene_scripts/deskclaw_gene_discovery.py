#!/usr/bin/env python3
"""DeskClaw Gene Discovery Tool -- search the gene market and request learning.

Usage:
  python3 deskclaw_gene_discovery.py <action> [options]

Actions:
  search [--keyword TEXT] [--tag TAG] [--category CAT]  Search genes
  get_detail --gene-id ID                              Get gene details
  get_tags                                             List available tags
  get_featured [--limit N]                             Get featured genes
  request_learning --gene-slug SLUG [--instance-id ID]  Request gene installation
  list_installed [--instance-id ID]                    List installed genes
  list_genomes [--keyword TEXT]                        Search genomes
  get_genome --genome-id ID                            Get genome details

Environment:
  DESKCLAW_API_URL        Backend API base URL
  DESKCLAW_TOKEN          Instance proxy_token
  DESKCLAW_WORKSPACE_ID   Workspace ID
  DESKCLAW_INSTANCE_ID    Current instance ID (for request_learning default)
"""

from __future__ import annotations

import argparse
import os

from _api_client import api_call, _output, _fatal


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="deskclaw_gene_discovery", description="DeskClaw Gene Discovery Tool")
    sub = p.add_subparsers(dest="action", required=True)

    default_iid = os.environ.get("DESKCLAW_INSTANCE_ID") or os.environ.get("NODESKCLAW_INSTANCE_ID", "")

    sp = sub.add_parser("search", help="Search genes")
    sp.add_argument("--keyword")
    sp.add_argument("--tag")
    sp.add_argument("--category")
    sp.add_argument("--sort", default="popularity")
    sp.add_argument("--page", type=int, default=1)
    sp.add_argument("--page-size", type=int, default=20)

    sp = sub.add_parser("get_detail", help="Get gene details")
    sp.add_argument("--gene-id", required=True)

    sub.add_parser("get_tags", help="List available tags")

    sp = sub.add_parser("get_featured", help="Get featured genes")
    sp.add_argument("--limit", type=int, default=10)

    sp = sub.add_parser("request_learning", help="Request gene installation on your instance")
    sp.add_argument("--gene-slug", required=True)
    sp.add_argument("--instance-id", default=default_iid)

    sp = sub.add_parser("list_installed", help="List installed genes")
    sp.add_argument("--instance-id", default=default_iid)

    sp = sub.add_parser("list_genomes", help="Search genomes")
    sp.add_argument("--keyword")
    sp.add_argument("--page", type=int, default=1)
    sp.add_argument("--page-size", type=int, default=20)

    sp = sub.add_parser("get_genome", help="Get genome details")
    sp.add_argument("--genome-id", required=True)

    return p


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    action = args.action

    if action == "search":
        params = [f"sort={args.sort}", f"page={args.page}", f"page_size={args.page_size}"]
        if args.keyword:
            params.append(f"keyword={args.keyword}")
        if args.tag:
            params.append(f"tag={args.tag}")
        if args.category:
            params.append(f"category={args.category}")
        qs = "&".join(params)
        _output(api_call("GET", f"/genes?{qs}", ws=False))

    elif action == "get_detail":
        _output(api_call("GET", f"/genes/{args.gene_id}", ws=False))

    elif action == "get_tags":
        _output(api_call("GET", "/genes/tags", ws=False))

    elif action == "get_featured":
        _output(api_call("GET", f"/genes/featured?limit={args.limit}", ws=False))

    elif action == "request_learning":
        iid = args.instance_id
        if not iid:
            _fatal("--instance-id is required (or set DESKCLAW_INSTANCE_ID or NODESKCLAW_INSTANCE_ID)")
        _output(api_call("POST", f"/instances/{iid}/genes/install", {"gene_slug": args.gene_slug}, ws=False))

    elif action == "list_installed":
        iid = args.instance_id
        if not iid:
            _fatal("--instance-id is required (or set DESKCLAW_INSTANCE_ID or NODESKCLAW_INSTANCE_ID)")
        _output(api_call("GET", f"/instances/{iid}/genes", ws=False))

    elif action == "list_genomes":
        params = [f"page={args.page}", f"page_size={args.page_size}"]
        if args.keyword:
            params.append(f"keyword={args.keyword}")
        qs = "&".join(params)
        _output(api_call("GET", f"/genomes?{qs}", ws=False))

    elif action == "get_genome":
        _output(api_call("GET", f"/genomes/{args.genome_id}", ws=False))


if __name__ == "__main__":
    main()
