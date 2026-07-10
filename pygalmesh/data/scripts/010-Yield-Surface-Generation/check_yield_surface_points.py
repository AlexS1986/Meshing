#!/usr/bin/env python3
import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path


def infer_sample_id(path, data):
    config_path = data.get("config_path")
    if config_path:
        try:
            with open(config_path) as handle:
                config = json.load(handle)
            sample_id = config.get("yield_surface", {}).get("sample_id")
            if sample_id:
                return sample_id
        except OSError:
            pass

    for part in path.parts:
        if part.startswith("ys_"):
            return part
    return None


def expected_from_manifest(jobs_dir):
    manifest = jobs_dir / "manifest.csv"
    if not manifest.is_file():
        return None

    with manifest.open(newline="") as handle:
        reader = csv.DictReader(handle)
        return [row["sample_id"] for row in reader if row.get("sample_id")]


def expected_from_job_dirs(jobs_dir):
    if not jobs_dir.is_dir():
        return []
    return sorted(path.name for path in jobs_dir.iterdir() if path.is_dir() and path.name.startswith("ys_"))


def iter_summary_files(project_dir, filename):
    yield from project_dir.glob(f"00_results/**/{filename}")
    yield from project_dir.glob(f"yield_surface_runs/**/{filename}")


def load_summary(path):
    with path.open() as handle:
        data = json.load(handle)

    final_state = data.get("final_yield_state") or {}
    current_eps = final_state.get("eps_mac_eigenvalues_current") or [None, None, None]
    return {
        "path": path,
        "sample_id": infer_sample_id(path, data),
        "stop_reason": data.get("stop_reason"),
        "current_eps": current_eps,
        "strain_scale": final_state.get("strain_scale"),
        "yielded_fraction": final_state.get("yielded_fraction_reduced_material_volume"),
        "has_point": all(value is not None for value in current_eps),
    }


def short_path(path, base):
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def main():
    parser = argparse.ArgumentParser(
        description="Check whether every expected yield-surface point has a generated yield_run JSON."
    )
    parser.add_argument("--project-dir", default=Path(__file__).resolve().parent)
    parser.add_argument("--points", type=int, default=48, help="Yield-surface job set, e.g. 48 for n048.")
    parser.add_argument("--jobs-dir", default=None, help="Defaults to yield_surface_jobs/nNNN.")
    parser.add_argument("--material", default="std")
    parser.add_argument("--direction", default="tensor")
    parser.add_argument(
        "--require-stop-reason",
        default=None,
        help="Optional required stop_reason, e.g. yielded_volume_fraction_reached.",
    )
    parser.add_argument("--csv", default=None, help="Optional path for a detailed CSV report.")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    jobs_dir = Path(args.jobs_dir).resolve() if args.jobs_dir else project_dir / "yield_surface_jobs" / f"n{args.points:03d}"
    filename = f"yield_run_{args.material}_{args.direction}.json"

    expected = expected_from_manifest(jobs_dir)
    expected_source = jobs_dir / "manifest.csv"
    if expected is None:
        expected = expected_from_job_dirs(jobs_dir)
        expected_source = jobs_dir

    if not expected:
        print(f"No expected sample points found in {jobs_dir}", file=sys.stderr)
        return 2

    summaries_by_sample = defaultdict(list)
    unreadable = []
    for path in sorted(iter_summary_files(project_dir, filename)):
        try:
            summary = load_summary(path)
        except (OSError, json.JSONDecodeError) as exc:
            unreadable.append((path, exc))
            continue
        if summary["sample_id"]:
            summaries_by_sample[summary["sample_id"]].append(summary)

    rows = []
    missing = []
    incomplete = []
    wrong_stop_reason = []

    for sample_id in expected:
        summaries = summaries_by_sample.get(sample_id, [])
        complete = [item for item in summaries if item["has_point"]]
        status = "ok" if complete else "missing"
        reason = ""
        best = complete[0] if complete else (summaries[0] if summaries else None)

        if not summaries:
            missing.append(sample_id)
            reason = "no summary JSON found"
        elif not complete:
            incomplete.append(sample_id)
            reason = "summary exists, but final_yield_state.eps_mac_eigenvalues_current is missing"
        elif args.require_stop_reason:
            bad = [item for item in complete if item["stop_reason"] != args.require_stop_reason]
            if bad:
                status = "bad_stop_reason"
                wrong_stop_reason.append(sample_id)
                reason = f"expected stop_reason={args.require_stop_reason}"

        rows.append({
            "sample_id": sample_id,
            "status": status,
            "summary_count": len(summaries),
            "complete_summary_count": len(complete),
            "stop_reason": best["stop_reason"] if best else "",
            "eps_1": best["current_eps"][0] if best else "",
            "eps_2": best["current_eps"][1] if best else "",
            "eps_3": best["current_eps"][2] if best else "",
            "strain_scale": best["strain_scale"] if best else "",
            "yielded_fraction": best["yielded_fraction"] if best else "",
            "summary_file": short_path(best["path"], project_dir) if best else "",
            "note": reason,
        })

    if args.csv:
        csv_path = Path(args.csv).resolve()
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with csv_path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    ok_count = sum(1 for row in rows if row["status"] == "ok")
    print(f"Expected points: {len(expected)} from {expected_source}")
    print(f"Result filename: {filename}")
    print(f"Generated points: {ok_count}/{len(expected)}")
    if args.csv:
        print(f"CSV report: {Path(args.csv).resolve()}")

    problems = [row for row in rows if row["status"] != "ok"]
    if problems:
        print("\nMissing/incomplete points:")
        for row in problems:
            print(
                f"  {row['sample_id']}: {row['status']}"
                f" ({row['note'] or row['stop_reason'] or 'see summary'})"
            )

    if unreadable:
        print("\nUnreadable summary files:")
        for path, exc in unreadable:
            print(f"  {short_path(path, project_dir)}: {exc}")

    return 1 if missing or incomplete or wrong_stop_reason or unreadable else 0


if __name__ == "__main__":
    raise SystemExit(main())
