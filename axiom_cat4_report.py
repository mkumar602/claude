#!/usr/bin/env python3
"""
Connect to a Nasdaq AxiomSL ControllerView (Axiom) server and download a
regulatory report for a Category IV bank holding company.

IMPORTANT
---------
Axiom's REST/web-service API is licensed per client and its URLs differ by
version and by how your firm deployed it. The endpoint paths below follow
a common pattern but are placeholders: check them against the API guide
from your Axiom admin or Nasdaq support and change ENDPOINTS if needed.

Typical Category IV (U.S. tailoring rule) reports produced in Axiom:
    FR Y-9C, FR Y-14A / Y-14Q / Y-14M, FR Y-15, FR 2052a (liquidity)

Usage
-----
    export AXIOM_BASE_URL="https://axiom.mybank.com/cv"
    export AXIOM_USER="svc_regrep"
    export AXIOM_PASSWORD="********"
    python axiom_cat4_report.py --report FRY9C --entity BHC001 --date 2026-06-30
"""

import argparse
import os
import sys
import time
from pathlib import Path

import requests

# Change these to match your Axiom API version.
ENDPOINTS = {
    "login":    "/api/v1/auth/login",
    "logout":   "/api/v1/auth/logout",
    "run":      "/api/v1/reports/{report}/run",
    "status":   "/api/v1/reports/jobs/{job_id}",
    "download": "/api/v1/reports/jobs/{job_id}/output",
}

# Report codes as they might be named in Axiom; use your own workspace names.
CATEGORY_IV_REPORTS = {
    "FRY9C":   "Consolidated Financial Statements for Holding Companies",
    "FRY14A":  "Capital Assessments and Stress Testing - Annual",
    "FRY14Q":  "Capital Assessments and Stress Testing - Quarterly",
    "FRY14M":  "Capital Assessments and Stress Testing - Monthly",
    "FRY15":   "Banking Organization Systemic Risk Report",
    "FR2052A": "Complex Institution Liquidity Monitoring Report",
}


class AxiomClient:
    def __init__(self, base_url, username, password, verify_ssl=True, timeout=60):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.timeout = timeout
        self.session = requests.Session()
        # True, False, or a path to your firm's CA bundle.
        self.session.verify = verify_ssl

    def _url(self, key, **kwargs):
        return self.base_url + ENDPOINTS[key].format(**kwargs)

    def login(self):
        resp = self.session.post(
            self._url("login"),
            json={"username": self.username, "password": self.password},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        token = resp.json().get("token")
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"
        # If your server uses a session cookie instead, requests.Session keeps it.
        print(f"Logged in to Axiom as {self.username}")

    def logout(self):
        try:
            self.session.post(self._url("logout"), timeout=self.timeout)
        except requests.RequestException:
            pass
        self.session.close()

    def run_report(self, report, entity, as_of_date, fmt):
        payload = {
            "entity": entity,          # legal entity / RSSD ID set up in Axiom
            "reportingDate": as_of_date,
            "outputFormat": fmt,       # e.g. XLSX, PDF, XML, CSV
        }
        resp = self.session.post(
            self._url("run", report=report), json=payload, timeout=self.timeout
        )
        resp.raise_for_status()
        job_id = resp.json()["jobId"]
        print(f"Report {report} submitted, job id {job_id}")
        return job_id

    def wait_for_job(self, job_id, poll_seconds=10, max_wait=1800):
        waited = 0
        while waited < max_wait:
            resp = self.session.get(
                self._url("status", job_id=job_id), timeout=self.timeout
            )
            resp.raise_for_status()
            status = resp.json().get("status", "").upper()
            print(f"  job {job_id}: {status}")
            if status in ("COMPLETED", "SUCCESS", "DONE"):
                return
            if status in ("FAILED", "ERROR", "CANCELLED"):
                raise RuntimeError(f"Axiom job {job_id} ended with status {status}")
            time.sleep(poll_seconds)
            waited += poll_seconds
        raise TimeoutError(f"Axiom job {job_id} did not finish in {max_wait}s")

    def download(self, job_id, out_path):
        with self.session.get(
            self._url("download", job_id=job_id), stream=True, timeout=self.timeout
        ) as resp:
            resp.raise_for_status()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    f.write(chunk)
        print(f"Saved report to {out_path}")
        return out_path


def parse_args():
    p = argparse.ArgumentParser(description="Download a Category IV bank report from Axiom")
    p.add_argument("--report", required=True, choices=sorted(CATEGORY_IV_REPORTS),
                   help="Report code")
    p.add_argument("--entity", required=True, help="Axiom entity code or RSSD ID")
    p.add_argument("--date", required=True, help="Reporting date, YYYY-MM-DD")
    p.add_argument("--format", default="XLSX", help="Output format (default XLSX)")
    p.add_argument("--out-dir", default="reports", help="Folder to save the file in")
    p.add_argument("--ca-bundle", help="Path to your firm's CA bundle for TLS")
    return p.parse_args()


def main():
    args = parse_args()

    base_url = os.environ.get("AXIOM_BASE_URL")
    user = os.environ.get("AXIOM_USER")
    password = os.environ.get("AXIOM_PASSWORD")
    if not all([base_url, user, password]):
        sys.exit("Set AXIOM_BASE_URL, AXIOM_USER and AXIOM_PASSWORD first.")

    client = AxiomClient(base_url, user, password, verify_ssl=args.ca_bundle or True)
    out_file = Path(args.out_dir) / (
        f"{args.report}_{args.entity}_{args.date}.{args.format.lower()}"
    )

    print(f"Category IV report: {args.report} - {CATEGORY_IV_REPORTS[args.report]}")
    try:
        client.login()
        job_id = client.run_report(args.report, args.entity, args.date, args.format)
        client.wait_for_job(job_id)
        client.download(job_id, out_file)
    except requests.HTTPError as e:
        sys.exit(f"Axiom API error: {e} - {e.response.text[:500]}")
    finally:
        client.logout()


if __name__ == "__main__":
    main()
