# Axiom Category IV Bank Report Downloader

A small Python script that connects to a Nasdaq AxiomSL ControllerView (Axiom)
server, runs a regulatory report for a Category IV bank holding company, and
downloads the result.

## Supported reports

| Code      | Report                                                   |
|-----------|----------------------------------------------------------|
| `FRY9C`   | Consolidated Financial Statements for Holding Companies  |
| `FRY14A`  | Capital Assessments and Stress Testing - Annual          |
| `FRY14Q`  | Capital Assessments and Stress Testing - Quarterly       |
| `FRY14M`  | Capital Assessments and Stress Testing - Monthly         |
| `FRY15`   | Banking Organization Systemic Risk Report                |
| `FR2052A` | Complex Institution Liquidity Monitoring Report          |

These codes are placeholders. Change them in `CATEGORY_IV_REPORTS` to the
report names used in your Axiom workspace.

## Requirements

- Python 3.8+
- Network access to your Axiom server
- An Axiom user allowed to run and export the reports

```bash
pip install -r requirements.txt
```

## Usage

Set your connection details as environment variables. The password is never
stored in the code.

```bash
export AXIOM_BASE_URL="https://axiom.yourbank.com/cv"
export AXIOM_USER="svc_regrep"
export AXIOM_PASSWORD="********"

python axiom_cat4_report.py --report FRY9C --entity BHC001 --date 2026-06-30
```

### Options

| Option        | Required | Description                                      |
|---------------|----------|--------------------------------------------------|
| `--report`    | yes      | Report code from the table above                 |
| `--entity`    | yes      | Axiom entity code or RSSD ID                     |
| `--date`      | yes      | Reporting date, `YYYY-MM-DD`                     |
| `--format`    | no       | Output format: `XLSX` (default), `PDF`, `XML`, `CSV` |
| `--out-dir`   | no       | Folder to save the file in (default `reports`)   |
| `--ca-bundle` | no       | Path to your firm's CA bundle for TLS            |

The file is saved as `reports/<REPORT>_<ENTITY>_<DATE>.<format>`.

## How it works

1. **Log in:** sends the username and password to the login endpoint, then
   uses the returned bearer token or session cookie.
2. **Run the report:** submits the report for the entity, date and format,
   and gets back a job ID.
3. **Wait:** checks the job every 10 seconds until it finishes or fails
   (30-minute limit).
4. **Download:** saves the output file, then logs out.

## Configuring for your Axiom server

Nasdaq does not publish a standard public API for Axiom. The API is licensed
per client, and its paths and field names depend on your version and setup.
Before first use, check these against the API guide from your Axiom admin or
Nasdaq support:

- The `ENDPOINTS` dict at the top of `axiom_cat4_report.py`
- The JSON field names the script reads: `token`, `jobId` and `status`
- The request fields it sends: `entity`, `reportingDate` and `outputFormat`

If your firm runs Axiom reports through command-line or batch tools rather
than a REST API, replace the web calls with `subprocess` calls to those tools.

## Security notes

- Keep credentials in environment variables or a secrets manager, never in code.
- If your firm uses its own certificates, pass `--ca-bundle`. Do not turn off
  TLS verification.
