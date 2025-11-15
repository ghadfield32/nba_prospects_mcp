#!/usr/bin/env python3
"""
LNB API Endpoint Health Monitoring Script

Purpose:
--------
Periodic health checks for all LNB API endpoints to detect API changes before they
break production code. Alerts when endpoints start returning unexpected status codes.

Features:
---------
1. Tests all known LNB API endpoints
2. Compares results against expected status codes
3. Generates health report (JSON + human-readable)
4. Detects newly broken or newly fixed endpoints
5. Lightweight and fast (< 30 seconds for all endpoints)

Usage:
------
    # Run health check
    python tools/lnb/monitor_lnb_endpoints.py

    # Run in CI/CD (exit code 1 if critical endpoints fail)
    python tools/lnb/monitor_lnb_endpoints.py --strict

    # Save report to custom location
    python tools/lnb/monitor_lnb_endpoints.py --output reports/lnb_health.json

    # Quiet mode (only show failures)
    python tools/lnb/monitor_lnb_endpoints.py --quiet

Created: 2025-11-15
Last Updated: 2025-11-15
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import requests

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class EndpointMonitor:
    """Monitor health of LNB API endpoints"""

    def __init__(self, headers_path: str = "tools/lnb/lnb_headers.json"):
        self.base_url = "https://api-prod.lnb.fr"
        self.headers = self._load_headers(headers_path)
        self.results = []
        self.timestamp = datetime.now().isoformat()

    def _load_headers(self, path: str) -> dict[str, str]:
        """Load HTTP headers from JSON file"""
        try:
            with open(path) as f:
                headers = json.load(f)
            logger.info(f"Loaded {len(headers)} headers from {path}")
            return headers
        except FileNotFoundError:
            logger.warning(f"Headers file not found: {path}, using minimal headers")
            return {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
            }

    def check_endpoint(
        self,
        name: str,
        path: str,
        method: str = "GET",
        params: dict[str, Any] = None,
        json_body: dict[str, Any] = None,
        expected_status: int = 200,
        critical: bool = True,
    ) -> dict[str, Any]:
        """
        Check a single endpoint

        Args:
            name: Endpoint name for reporting
            path: API path (e.g., "/common/getAllYears")
            method: HTTP method (GET, POST)
            params: Query parameters
            json_body: JSON body for POST requests
            expected_status: Expected HTTP status code
            critical: If True, failure counts as critical

        Returns:
            Dict with test results
        """
        url = f"{self.base_url}{path}"

        try:
            if method.upper() == "GET":
                response = requests.get(url, params=params, headers=self.headers, timeout=10)
            elif method.upper() == "POST":
                response = requests.post(
                    url, params=params, json=json_body, headers=self.headers, timeout=10
                )
            else:
                raise ValueError(f"Unsupported method: {method}")

            status_code = response.status_code
            success = status_code == expected_status

            result = {
                "name": name,
                "path": path,
                "method": method,
                "expected_status": expected_status,
                "actual_status": status_code,
                "success": success,
                "critical": critical,
                "response_size": len(response.text),
                "timestamp": datetime.now().isoformat(),
            }

            # Add error details if failed
            if not success:
                result["error"] = {
                    "message": f"Expected {expected_status}, got {status_code}",
                    "response": response.text[:200],
                }

            return result

        except Exception as e:
            return {
                "name": name,
                "path": path,
                "method": method,
                "expected_status": expected_status,
                "actual_status": None,
                "success": False,
                "critical": critical,
                "timestamp": datetime.now().isoformat(),
                "error": {"message": str(e), "type": type(e).__name__},
            }

    def run_all_checks(self) -> None:
        """Run health checks on all known endpoints"""
        logger.info("Starting LNB API endpoint health checks...")

        # =====================================================================
        # CRITICAL ENDPOINTS (should always work)
        # =====================================================================

        # Structure / Discovery
        self.results.append(
            self.check_endpoint(
                name="getAllYears",
                path="/common/getAllYears",
                method="GET",
                expected_status=200,
                critical=True,
            )
        )

        self.results.append(
            self.check_endpoint(
                name="getEventList",
                path="/event/getEventList",
                method="GET",
                expected_status=200,
                critical=True,
            )
        )

        self.results.append(
            self.check_endpoint(
                name="getDivisionCompetitionByYear",
                path="/common/getDivisionCompetitionByYear",
                method="GET",
                params={"year": 2025, "division_external_id": 1},
                expected_status=200,
                critical=True,
            )
        )

        # Live / Schedule
        self.results.append(
            self.check_endpoint(
                name="getLiveMatch",
                path="/match/getLiveMatch",
                method="GET",
                expected_status=200,
                critical=True,
            )
        )

        self.results.append(
            self.check_endpoint(
                name="getCalenderByDivision",  # Note typo in actual API
                path="/match/getCalenderByDivision",
                method="GET",
                params={"division_external_id": 1, "year": 2025},
                expected_status=200,
                critical=True,
            )
        )

        self.results.append(
            self.check_endpoint(
                name="getCalendar",
                path="/stats/getCalendar",
                method="POST",
                json_body={
                    "from": (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"),
                    "to": datetime.now().strftime("%Y-%m-%d"),
                },
                expected_status=200,
                critical=True,
            )
        )

        # =====================================================================
        # DEPRECATED ENDPOINTS (should return 404)
        # =====================================================================

        self.results.append(
            self.check_endpoint(
                name="getMainCompetition (DEPRECATED)",
                path="/common/getMainCompetition",
                method="GET",
                params={"year": 2025},
                expected_status=404,  # Expected to be broken
                critical=False,
            )
        )

        # =====================================================================
        # NON-CRITICAL ENDPOINTS (nice to have, but OK if down)
        # =====================================================================

        self.results.append(
            self.check_endpoint(
                name="getCompetitionTeams",
                path="/stats/getCompetitionTeams",
                method="GET",
                params={"competition_external_id": 302},  # Current season
                expected_status=200,
                critical=False,
            )
        )

        self.results.append(
            self.check_endpoint(
                name="getStanding",
                path="/stats/getStanding",
                method="POST",
                json_body={"competitionExternalId": 302},
                expected_status=200,
                critical=False,
            )
        )

        self.results.append(
            self.check_endpoint(
                name="getTeamComparison",
                path="/stats/getTeamComparison",
                method="POST",
                json_body={"match_external_id": 28931},  # Example match
                expected_status=200,
                critical=False,
            )
        )

        logger.info(f"Completed {len(self.results)} endpoint checks")

    def generate_report(self) -> dict[str, Any]:
        """Generate health report from check results"""
        total = len(self.results)
        passed = len([r for r in self.results if r["success"]])
        failed = total - passed
        critical_failed = len([r for r in self.results if not r["success"] and r["critical"]])

        report = {
            "timestamp": self.timestamp,
            "summary": {
                "total_endpoints": total,
                "passed": passed,
                "failed": failed,
                "critical_failed": critical_failed,
                "success_rate": round(passed / total * 100, 1) if total > 0 else 0,
                "health_status": "HEALTHY" if critical_failed == 0 else "DEGRADED",
            },
            "endpoints": self.results,
            "recommendations": [],
        }

        # Add recommendations based on failures
        for result in self.results:
            if not result["success"] and result["critical"]:
                report["recommendations"].append(
                    {
                        "endpoint": result["name"],
                        "issue": f"Critical endpoint {result['name']} is down",
                        "action": "Investigate immediately - core functionality may be affected",
                    }
                )

        return report

    def print_report(self, report: dict[str, Any], quiet: bool = False) -> None:
        """Print human-readable report"""
        summary = report["summary"]

        if not quiet:
            print("\n" + "=" * 80)
            print("LNB API ENDPOINT HEALTH REPORT")
            print("=" * 80)
            print(f"\nTimestamp: {report['timestamp']}")
            print(f"Status: {summary['health_status']}")
            print(
                f"\nResults: {summary['passed']}/{summary['total_endpoints']} passed ({summary['success_rate']}%)"
            )
            print(f"Critical Failures: {summary['critical_failed']}")
            print("\n" + "-" * 80)
            print("ENDPOINT DETAILS")
            print("-" * 80)

        for result in report["endpoints"]:
            if quiet and result["success"]:
                continue  # Skip successful tests in quiet mode

            status_icon = "[OK]" if result["success"] else "[FAIL]"
            critical_marker = " [CRITICAL]" if result["critical"] else ""

            print(f"\n{status_icon} {result['name']}{critical_marker}")
            print(f"   Path: {result['method']} {result['path']}")
            print(
                f"   Expected: HTTP {result['expected_status']}, Got: HTTP {result.get('actual_status', 'N/A')}"
            )

            if not result["success"] and "error" in result:
                print(f"   Error: {result['error'].get('message', 'Unknown error')}")

        if report["recommendations"]:
            print("\n" + "-" * 80)
            print("RECOMMENDATIONS")
            print("-" * 80)
            for rec in report["recommendations"]:
                print(f"\n[WARNING] {rec['issue']}")
                print(f"   Action: {rec['action']}")

        print("\n" + "=" * 80)

    def save_report(self, report: dict[str, Any], output_path: str) -> None:
        """Save report to JSON file"""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        logger.info(f"Report saved to {output_path}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Monitor LNB API endpoint health")
    parser.add_argument(
        "--output",
        "-o",
        default="tools/lnb/reports/lnb_endpoint_health.json",
        help="Output path for JSON report",
    )
    parser.add_argument(
        "--strict", action="store_true", help="Exit with code 1 if any critical endpoints fail"
    )
    parser.add_argument(
        "--quiet", "-q", action="store_true", help="Only show failures (quiet mode)"
    )
    args = parser.parse_args()

    # Run monitoring
    monitor = EndpointMonitor()
    monitor.run_all_checks()

    # Generate and display report
    report = monitor.generate_report()
    monitor.print_report(report, quiet=args.quiet)

    # Save report
    monitor.save_report(report, args.output)

    # Exit with error code if strict mode and critical failures
    if args.strict and report["summary"]["critical_failed"] > 0:
        logger.error(f"Critical failures detected: {report['summary']['critical_failed']}")
        sys.exit(1)

    logger.info("Health check complete")
    sys.exit(0)


if __name__ == "__main__":
    main()
