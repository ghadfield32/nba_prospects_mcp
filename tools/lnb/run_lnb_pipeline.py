#!/usr/bin/env python3
"""LNB Data Pipeline - End-to-End Orchestration

Runs the complete LNB data pipeline:
1. Build truthful game index (if needed)
2. Build curated datasets (PBP + Shots)
3. Run reconciliation gate
4. Generate pipeline report

Usage:
    # Run full pipeline for all seasons
    python tools/lnb/run_lnb_pipeline.py

    # Run for specific season
    python tools/lnb/run_lnb_pipeline.py --season 2023-2024

    # Force rebuild everything
    python tools/lnb/run_lnb_pipeline.py --season 2023-2024 --force-rebuild

    # Skip index building (use existing)
    python tools/lnb/run_lnb_pipeline.py --season 2023-2024 --skip-index

    # Skip curated building (use existing)
    python tools/lnb/run_lnb_pipeline.py --season 2023-2024 --skip-curated

    # Dry run (show what would be done)
    python tools/lnb/run_lnb_pipeline.py --season 2023-2024 --dry-run
"""

import argparse
import io
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class PipelineError(Exception):
    """Raised when pipeline stage fails"""

    pass


class PipelineStage:
    """Represents a single pipeline stage"""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.status = "pending"
        self.duration_seconds = None
        self.error_message = None
        self.output = None

    def mark_running(self):
        self.status = "running"
        self._start_time = datetime.now()

    def mark_success(self, output: str | None = None):
        self.status = "success"
        self.output = output
        if hasattr(self, "_start_time"):
            self.duration_seconds = (datetime.now() - self._start_time).total_seconds()

    def mark_failed(self, error: str):
        self.status = "failed"
        self.error_message = error
        if hasattr(self, "_start_time"):
            self.duration_seconds = (datetime.now() - self._start_time).total_seconds()

    def mark_skipped(self, reason: str):
        self.status = "skipped"
        self.error_message = reason

    def to_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "duration_seconds": self.duration_seconds,
            "error_message": self.error_message,
        }


def print_stage_header(stage: PipelineStage, stage_num: int, total_stages: int):
    """Print stage header"""
    print("\n" + "=" * 80)
    print(f"  STAGE {stage_num}/{total_stages}: {stage.name.upper()}")
    print("=" * 80)
    print(f"{stage.description}")
    print()


def print_stage_result(stage: PipelineStage):
    """Print stage result"""
    if stage.status == "success":
        icon = "✅"
        status = "SUCCESS"
    elif stage.status == "failed":
        icon = "❌"
        status = "FAILED"
    elif stage.status == "skipped":
        icon = "⏭️"
        status = "SKIPPED"
    else:
        icon = "⏳"
        status = "UNKNOWN"

    print(f"\n{icon} Stage {status}")
    if stage.duration_seconds is not None:
        print(f"   Duration: {stage.duration_seconds:.1f}s")
    if stage.error_message:
        print(f"   Reason: {stage.error_message}")
    print()


def run_command(cmd: list[str], stage: PipelineStage, dry_run: bool = False) -> bool:
    """Run a command and track results in stage

    Args:
        cmd: Command to run (list of strings)
        stage: PipelineStage to update
        dry_run: If True, just print command without running

    Returns:
        True if successful, False otherwise
    """
    stage.mark_running()

    if dry_run:
        print(f"[DRY RUN] Would execute: {' '.join(cmd)}")
        stage.mark_success(output="[dry run - not executed]")
        return True

    print(f"[INFO] Running: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=False, encoding="utf-8", errors="replace"
        )

        # Print output in real-time style
        if result.stdout:
            print(result.stdout)

        if result.returncode == 0:
            stage.mark_success(output=result.stdout)
            return True
        else:
            # Command failed
            error_msg = result.stderr if result.stderr else "Command exited with non-zero status"
            if result.stderr:
                print(result.stderr, file=sys.stderr)
            stage.mark_failed(error_msg)
            return False

    except Exception as e:
        stage.mark_failed(str(e))
        print(f"[ERROR] Failed to run command: {e}", file=sys.stderr)
        return False


def build_game_index(
    season: str | None, force_rebuild: bool, skip_index: bool, dry_run: bool
) -> PipelineStage:
    """Stage 1: Build game index"""
    stage = PipelineStage(
        name="Build Game Index", description="Build truthful game index from fixture discovery"
    )

    if skip_index:
        stage.mark_skipped("--skip-index flag set")
        return stage

    # Check if index already exists
    index_path = Path("data/raw/lnb/lnb_game_index.parquet")
    if index_path.exists() and not force_rebuild:
        stage.mark_skipped("Index already exists (use --force-rebuild to rebuild)")
        return stage

    # Build command
    cmd = [
        sys.executable,
        "tools/lnb/build_game_index.py",
    ]

    if season:
        cmd.extend(["--seasons", season])

    if force_rebuild:
        cmd.append("--force-rebuild")

    # Run command
    success = run_command(cmd, stage, dry_run)

    if not success and not dry_run:
        raise PipelineError(f"Failed to build game index: {stage.error_message}")

    return stage


def build_curated_pbp(
    season: str, force_rebuild: bool, skip_curated: bool, dry_run: bool
) -> PipelineStage:
    """Stage 2a: Build curated PBP dataset"""
    stage = PipelineStage(
        name="Build Curated PBP",
        description=f"Build combined PBP dataset for {season} with content validation",
    )

    if skip_curated:
        stage.mark_skipped("--skip-curated flag set")
        return stage

    # Check if curated already exists
    curated_path = Path(f"data/curated/lnb/pbp/season={season}/lnb_pbp.parquet")
    if curated_path.exists() and not force_rebuild:
        stage.mark_skipped("Curated PBP already exists (use --force-rebuild to rebuild)")
        return stage

    # Build command
    cmd = [
        sys.executable,
        "tools/lnb/build_lnb_combined_pbp.py",
        "--season",
        season,
    ]

    if force_rebuild:
        cmd.append("--force")

    # Run command
    success = run_command(cmd, stage, dry_run)

    if not success and not dry_run:
        raise PipelineError(f"Failed to build curated PBP: {stage.error_message}")

    return stage


def build_curated_shots(
    season: str, force_rebuild: bool, skip_curated: bool, dry_run: bool
) -> PipelineStage:
    """Stage 2b: Build curated Shots dataset"""
    stage = PipelineStage(
        name="Build Curated Shots",
        description=f"Build combined Shots dataset for {season} with content validation",
    )

    if skip_curated:
        stage.mark_skipped("--skip-curated flag set")
        return stage

    # Check if curated already exists
    curated_path = Path(f"data/curated/lnb/shots/season={season}/lnb_shots.parquet")
    if curated_path.exists() and not force_rebuild:
        stage.mark_skipped("Curated Shots already exists (use --force-rebuild to rebuild)")
        return stage

    # Build command
    cmd = [
        sys.executable,
        "tools/lnb/build_lnb_combined_shots.py",
        "--season",
        season,
    ]

    if force_rebuild:
        cmd.append("--force")

    # Run command
    success = run_command(cmd, stage, dry_run)

    if not success and not dry_run:
        raise PipelineError(f"Failed to build curated Shots: {stage.error_message}")

    return stage


def run_reconciliation(season: str | None, dry_run: bool) -> PipelineStage:
    """Stage 3: Run reconciliation gate"""
    stage = PipelineStage(
        name="Run Reconciliation",
        description="Validate data quality across index, raw, and curated layers",
    )

    # Build command
    cmd = [
        sys.executable,
        "tools/lnb/reconcile_lnb.py",
    ]

    if season:
        cmd.extend(["--season", season])

    # Always save reconciliation results to JSON
    results_file = f"reconciliation_results_{season if season else 'all'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    cmd.extend(["--json-output", results_file])

    # Run command
    success = run_command(cmd, stage, dry_run)

    if not success and not dry_run:
        # Reconciliation failure is a warning, not a hard error
        # We still want to see the report
        print(f"\n[WARNING] Reconciliation found issues - check {results_file} for details")

    return stage


def generate_pipeline_report(
    stages: list[PipelineStage], season: str | None, start_time: datetime
) -> dict:
    """Generate final pipeline report"""
    end_time = datetime.now()
    total_duration = (end_time - start_time).total_seconds()

    # Count statuses
    total_stages = len(stages)
    successful = sum(1 for s in stages if s.status == "success")
    failed = sum(1 for s in stages if s.status == "failed")
    skipped = sum(1 for s in stages if s.status == "skipped")

    # Determine overall status
    if failed > 0:
        overall_status = "failed"
    elif successful == total_stages:
        overall_status = "success"
    elif successful + skipped == total_stages:
        overall_status = "partial_success"
    else:
        overall_status = "unknown"

    report = {
        "pipeline": "LNB Data Pipeline",
        "season": season or "all",
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "total_duration_seconds": total_duration,
        "overall_status": overall_status,
        "stages": {
            "total": total_stages,
            "successful": successful,
            "failed": failed,
            "skipped": skipped,
        },
        "stage_details": [s.to_dict() for s in stages],
    }

    return report


def print_pipeline_summary(report: dict):
    """Print pipeline summary"""
    print("\n" + "=" * 80)
    print("  PIPELINE SUMMARY")
    print("=" * 80)

    print(f"\nSeason: {report['season']}")
    print(f"Duration: {report['total_duration_seconds']:.1f}s")
    print(f"Overall Status: {report['overall_status'].upper()}")

    print("\nStages:")
    print(f"  ✅ Success: {report['stages']['successful']}")
    print(f"  ❌ Failed: {report['stages']['failed']}")
    print(f"  ⏭️  Skipped: {report['stages']['skipped']}")

    # Print failed stages
    failed_stages = [s for s in report["stage_details"] if s["status"] == "failed"]
    if failed_stages:
        print("\nFailed Stages:")
        for stage in failed_stages:
            print(f"  ❌ {stage['name']}: {stage['error_message']}")

    # Overall result
    print("\n" + "=" * 80)
    if report["overall_status"] == "success":
        print("✅ PIPELINE COMPLETED SUCCESSFULLY")
    elif report["overall_status"] == "partial_success":
        print("⚠️  PIPELINE COMPLETED WITH SOME STAGES SKIPPED")
    else:
        print("❌ PIPELINE FAILED")
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="LNB Data Pipeline - End-to-End Orchestration")
    parser.add_argument(
        "--season",
        help="Run pipeline for specific season (e.g., 2023-2024). If not specified, runs for all seasons.",
    )
    parser.add_argument(
        "--force-rebuild",
        action="store_true",
        help="Force rebuild of all stages, even if outputs already exist",
    )
    parser.add_argument(
        "--skip-index", action="store_true", help="Skip game index building (use existing index)"
    )
    parser.add_argument(
        "--skip-curated",
        action="store_true",
        help="Skip curated dataset building (use existing curated)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually running commands",
    )
    parser.add_argument("--report-output", help="Save pipeline report to JSON file")

    args = parser.parse_args()

    # Determine seasons to process
    if args.season:
        seasons = [args.season]
    else:
        # Default to known complete seasons
        seasons = ["2022-2023", "2023-2024"]
        print(f"[INFO] No season specified, running for: {', '.join(seasons)}")

    # Pipeline start
    print("\n" + "=" * 80)
    print("  LNB DATA PIPELINE")
    print("=" * 80)
    print(f"\nSeasons: {', '.join(seasons)}")
    print(f"Force Rebuild: {args.force_rebuild}")
    print(f"Skip Index: {args.skip_index}")
    print(f"Skip Curated: {args.skip_curated}")
    if args.dry_run:
        print("\n[DRY RUN MODE - No changes will be made]")
    print()

    start_time = datetime.now()
    all_stages = []

    try:
        # Stage 1: Build Game Index
        print_stage_header(PipelineStage("Build Game Index", ""), 1, 4)
        index_stage = build_game_index(
            season=args.season,
            force_rebuild=args.force_rebuild,
            skip_index=args.skip_index,
            dry_run=args.dry_run,
        )
        all_stages.append(index_stage)
        print_stage_result(index_stage)

        # Stage 2: Build Curated Datasets (per season)
        for season in seasons:
            # Stage 2a: PBP
            print_stage_header(PipelineStage(f"Build Curated PBP ({season})", ""), 2, 4)
            pbp_stage = build_curated_pbp(
                season=season,
                force_rebuild=args.force_rebuild,
                skip_curated=args.skip_curated,
                dry_run=args.dry_run,
            )
            all_stages.append(pbp_stage)
            print_stage_result(pbp_stage)

            # Stage 2b: Shots
            print_stage_header(PipelineStage(f"Build Curated Shots ({season})", ""), 2, 4)
            shots_stage = build_curated_shots(
                season=season,
                force_rebuild=args.force_rebuild,
                skip_curated=args.skip_curated,
                dry_run=args.dry_run,
            )
            all_stages.append(shots_stage)
            print_stage_result(shots_stage)

        # Stage 3: Run Reconciliation
        print_stage_header(PipelineStage("Run Reconciliation", ""), 3, 4)
        reconcile_stage = run_reconciliation(season=args.season, dry_run=args.dry_run)
        all_stages.append(reconcile_stage)
        print_stage_result(reconcile_stage)

        # Stage 4: Generate Report
        report = generate_pipeline_report(
            stages=all_stages, season=args.season, start_time=start_time
        )

        print_pipeline_summary(report)

        # Save report if requested
        if args.report_output:
            with open(args.report_output, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            print(f"\n[INFO] Pipeline report saved to {args.report_output}")

        # Determine exit code
        if report["overall_status"] == "failed":
            return 1
        else:
            return 0

    except PipelineError as e:
        print("\n" + "=" * 80)
        print("  PIPELINE FAILED ❌")
        print("=" * 80)
        print(f"\nError: {e}")

        # Still generate report for failed pipeline
        report = generate_pipeline_report(
            stages=all_stages, season=args.season, start_time=start_time
        )
        print_pipeline_summary(report)

        if args.report_output:
            with open(args.report_output, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)

        return 1

    except Exception as e:
        print("\n" + "=" * 80)
        print("  UNEXPECTED ERROR ❌")
        print("=" * 80)
        print(f"\nError: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
