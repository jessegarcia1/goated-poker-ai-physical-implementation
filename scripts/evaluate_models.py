"""Evaluate one or more checkpoints with reproducible settings."""

import argparse
import csv
import json
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import torch

from src.agents.random_agent import RandomAgent
from src.utils.agents import create_agent_for_checkpoint
from src.utils.checkpoints import find_checkpoints
from src.utils.evaluation import empty_evaluation_metrics, evaluate_agent_matchup


def set_reproducible_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def resolve_device(device: str) -> str:
    if device == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    return device


def resolve_checkpoint_paths(
    checkpoints: Optional[Sequence[str]],
    checkpoint_dir: Optional[str],
    pattern: str,
) -> List[Path]:
    resolved: List[Path] = []

    if checkpoints:
        resolved.extend(Path(path) for path in checkpoints)

    if checkpoint_dir:
        resolved.extend(find_checkpoints(checkpoint_dir, pattern))

    unique_paths = []
    seen = set()
    for path in resolved:
        path = path.resolve()
        if path not in seen:
            seen.add(path)
            unique_paths.append(path)

    if not unique_paths:
        raise ValueError("No checkpoints provided. Use --checkpoints or --checkpoint-dir.")

    missing = [str(path) for path in unique_paths if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Checkpoint(s) not found: {', '.join(missing)}")

    return unique_paths


def load_positioned_agent(checkpoint_path: Path, player_id: int, device: str):
    return create_agent_for_checkpoint(checkpoint_path, player_id=player_id, device=device)


def build_agent_bank(checkpoint_paths: Sequence[Path], device: str) -> Dict[Path, List[Any]]:
    return {
        checkpoint_path: [
            load_positioned_agent(checkpoint_path, player_id=player_id, device=device)
            for player_id in range(6)
        ]
        for checkpoint_path in checkpoint_paths
    }


def create_random_opponents(num_players: int, player_id: int) -> List[Optional[Any]]:
    opponents = []
    for position in range(num_players):
        opponents.append(None if position == player_id else RandomAgent(position))
    return opponents


def create_checkpoint_pool_opponents(
    checkpoint_path: Path,
    agent_bank: Dict[Path, List[Any]],
    player_id: int,
) -> List[Optional[Any]]:
    pool_paths = [path for path in agent_bank if path != checkpoint_path]
    if not pool_paths:
        pool_paths = [checkpoint_path]

    opponents: List[Optional[Any]] = [None] * 6
    pool_index = 0
    for position in range(6):
        if position == player_id:
            continue
        pool_path = pool_paths[pool_index % len(pool_paths)]
        opponents[position] = agent_bank[pool_path][position]
        pool_index += 1
    return opponents


def evaluate_agent(
    agent,
    opponents: Sequence[Optional[Any]],
    *,
    num_games: int,
    seed_start: int,
    stake: float,
    sb: float,
    bb: float,
    strict: bool,
    label: str,
) -> Dict[str, Any]:
    return evaluate_agent_matchup(
        agent,
        opponents,
        num_games=num_games,
        seed_start=seed_start,
        stake=stake,
        sb=sb,
        bb=bb,
        strict=strict,
        label=label,
    )


def evaluate_checkpoint_paths(
    checkpoint_paths: Sequence[Path],
    *,
    games_random: int,
    games_pool: int,
    seed: int,
    device: str,
    strict: bool,
    stake: float,
    sb: float,
    bb: float,
) -> List[dict]:
    device = resolve_device(device)
    agent_bank = build_agent_bank(checkpoint_paths, device)
    results = []

    for checkpoint_path in checkpoint_paths:
        player_id = 0
        target_agent = agent_bank[checkpoint_path][player_id]
        checkpoint_result = {
            "checkpoint": str(checkpoint_path),
            "name": checkpoint_path.name,
            "iteration": int(target_agent.iteration_count),
            "device": device,
        }

        if games_random > 0:
            set_reproducible_seed(seed)
            random_metrics = evaluate_agent(
                target_agent,
                create_random_opponents(num_players=6, player_id=player_id),
                num_games=games_random,
                seed_start=seed,
                stake=stake,
                sb=sb,
                bb=bb,
                strict=strict,
                label=f"evaluation vs random for {checkpoint_path.name}",
            )
        else:
            random_metrics = empty_evaluation_metrics(0)

        if games_pool > 0:
            set_reproducible_seed(seed + 1)
            pool_metrics = evaluate_agent(
                target_agent,
                create_checkpoint_pool_opponents(checkpoint_path, agent_bank, player_id),
                num_games=games_pool,
                seed_start=seed + 100_000,
                stake=stake,
                sb=sb,
                bb=bb,
                strict=strict,
                label=f"evaluation vs checkpoint pool for {checkpoint_path.name}",
            )
        else:
            pool_metrics = empty_evaluation_metrics(0)

        checkpoint_result["vs_random"] = random_metrics
        checkpoint_result["vs_checkpoint_pool"] = pool_metrics
        results.append(checkpoint_result)

    return results


def print_results_table(results: Sequence[dict]) -> None:
    headers = [
        "checkpoint",
        "iter",
        "rand_profit",
        "rand_done",
        "rand_invalid",
        "rand_sanitized",
        "pool_profit",
        "pool_done",
        "pool_invalid",
        "pool_sanitized",
    ]
    rows = []
    for result in results:
        rows.append(
            [
                result["name"],
                str(result["iteration"]),
                f'{result["vs_random"]["avg_profit"]:.2f}',
                str(result["vs_random"]["completed_games"]),
                str(result["vs_random"]["invalid_state_count"]),
                str(result["vs_random"]["sanitized_actions"]),
                f'{result["vs_checkpoint_pool"]["avg_profit"]:.2f}',
                str(result["vs_checkpoint_pool"]["completed_games"]),
                str(result["vs_checkpoint_pool"]["invalid_state_count"]),
                str(result["vs_checkpoint_pool"]["sanitized_actions"]),
            ]
        )

    widths = [
        max(len(header), *(len(row[idx]) for row in rows))
        for idx, header in enumerate(headers)
    ]

    def format_row(row: Sequence[str]) -> str:
        return "  ".join(value.ljust(widths[idx]) for idx, value in enumerate(row))

    print(format_row(headers))
    print(format_row(["-" * width for width in widths]))
    for row in rows:
        print(format_row(row))


def write_json_results(results: Sequence[dict], output_path: str) -> None:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(list(results), indent=2), encoding="utf-8")

def write_csv_results(results: Sequence[dict], output_path: str) -> None:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "checkpoint",
        "name",
        "iteration",
        "device",
        "vs_random_avg_profit",
        "vs_random_completed_games",
        "vs_random_invalid_state_games",
        "vs_random_invalid_state_count",
        "vs_random_non_zero_sum_games",
        "vs_random_setup_errors",
        "vs_random_requested_games",
        "vs_random_sanitized_actions",
        "vs_random_agent_actions",
        "vs_random_agent_fold_actions",
        "vs_random_agent_check_call_actions",
        "vs_random_agent_raise_actions",
        "vs_random_agent_fold_rate",
        "vs_random_agent_check_call_rate",
        "vs_random_agent_raise_rate",
        "vs_random_agent_preflop_actions",
        "vs_random_agent_preflop_folds",
        "vs_random_agent_preflop_fold_rate",
        "vs_checkpoint_pool_avg_profit",
        "vs_checkpoint_pool_completed_games",
        "vs_checkpoint_pool_invalid_state_games",
        "vs_checkpoint_pool_invalid_state_count",
        "vs_checkpoint_pool_non_zero_sum_games",
        "vs_checkpoint_pool_setup_errors",
        "vs_checkpoint_pool_requested_games",
        "vs_checkpoint_pool_sanitized_actions",
        "vs_checkpoint_pool_agent_actions",
        "vs_checkpoint_pool_agent_fold_actions",
        "vs_checkpoint_pool_agent_check_call_actions",
        "vs_checkpoint_pool_agent_raise_actions",
        "vs_checkpoint_pool_agent_fold_rate",
        "vs_checkpoint_pool_agent_check_call_rate",
        "vs_checkpoint_pool_agent_raise_rate",
        "vs_checkpoint_pool_agent_preflop_actions",
        "vs_checkpoint_pool_agent_preflop_folds",
        "vs_checkpoint_pool_agent_preflop_fold_rate",
    ]

    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            row = {
                "checkpoint": result["checkpoint"],
                "name": result["name"],
                "iteration": result["iteration"],
                "device": result["device"],
            }
            for prefix, key in (
                ("vs_random", "vs_random"),
                ("vs_checkpoint_pool", "vs_checkpoint_pool"),
            ):
                m = result[key]
                row.update(
                    {
                        f"{prefix}_avg_profit": m["avg_profit"],
                        f"{prefix}_completed_games": m["completed_games"],
                        f"{prefix}_invalid_state_games": m["invalid_state_games"],
                        f"{prefix}_invalid_state_count": m["invalid_state_count"],
                        f"{prefix}_non_zero_sum_games": m["non_zero_sum_games"],
                        f"{prefix}_setup_errors": m["setup_errors"],
                        f"{prefix}_requested_games": m["requested_games"],
                        f"{prefix}_sanitized_actions": m["sanitized_actions"],
                        f"{prefix}_agent_actions": m["agent_actions"],
                        f"{prefix}_agent_fold_actions": m["agent_fold_actions"],
                        f"{prefix}_agent_check_call_actions": m["agent_check_call_actions"],
                        f"{prefix}_agent_raise_actions": m["agent_raise_actions"],
                        f"{prefix}_agent_fold_rate": m["agent_fold_rate"],
                        f"{prefix}_agent_check_call_rate": m["agent_check_call_rate"],
                        f"{prefix}_agent_raise_rate": m["agent_raise_rate"],
                        f"{prefix}_agent_preflop_actions": m["agent_preflop_actions"],
                        f"{prefix}_agent_preflop_folds": m["agent_preflop_folds"],
                        f"{prefix}_agent_preflop_fold_rate": m["agent_preflop_fold_rate"],
                    }
                )
            writer.writerow(row)

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate Deep CFR checkpoints.")
    parser.add_argument("--checkpoints", nargs="*", default=None, help="Explicit checkpoint paths to evaluate")
    parser.add_argument("--checkpoint-dir", type=str, default=None, help="Directory containing checkpoint files")
    parser.add_argument("--pattern", type=str, default="*.pt", help="Glob pattern for --checkpoint-dir")
    parser.add_argument("--games-random", type=int, default=100, help="Hands to play against random opponents")
    parser.add_argument("--games-pool", type=int, default=100, help="Hands to play against the checkpoint pool")
    parser.add_argument("--seed", type=int, default=0, help="Base random seed for reproducible evaluation")
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto", help="Inference device")
    parser.add_argument("--strict", action="store_true", help="Raise immediately on invalid game states (default)")
    parser.add_argument("--allow-invalid-games", action="store_true", help="Continue after invalid games and report error counts")
    parser.add_argument("--stake", type=float, default=200.0, help="Initial stake for each player")
    parser.add_argument("--sb", type=float, default=1.0, help="Small blind")
    parser.add_argument("--bb", type=float, default=2.0, help="Big blind")
    parser.add_argument("--json-out", type=str, default=None, help="Optional path for JSON results")
    parser.add_argument("--csv-out", type=str, default=None, help="Optional path for CSV results")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.strict and args.allow_invalid_games:
        parser.error("--strict and --allow-invalid-games cannot be combined")

    checkpoint_paths = resolve_checkpoint_paths(args.checkpoints, args.checkpoint_dir, args.pattern)
    results = evaluate_checkpoint_paths(
        checkpoint_paths,
        games_random=args.games_random,
        games_pool=args.games_pool,
        seed=args.seed,
        device=args.device,
        strict=not args.allow_invalid_games,
        stake=args.stake,
        sb=args.sb,
        bb=args.bb,
    )

    print_results_table(results)

    if args.json_out:
        write_json_results(results, args.json_out)
    if args.csv_out:
        write_csv_results(results, args.csv_out)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
