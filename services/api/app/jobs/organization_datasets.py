from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

from app.jobs.organization_universe import OrganizationRecord, normalize_domain


@dataclass(frozen=True)
class DatasetDescriptor:
    key: str
    owner: str
    default_organization_type: str
    source_url: str | None = None
    access_note: str | None = None


DATASETS: dict[str, DatasetDescriptor] = {
    "sec": DatasetDescriptor(
        key="SEC_EDGAR",
        owner="U.S. Securities and Exchange Commission",
        default_organization_type="PUBLIC_COMPANY",
        source_url="https://www.sec.gov/files/company_tickers_exchange.json",
        access_note="Public SEC company metadata; operators must follow SEC fair-access requirements.",
    ),
    "ipeds": DatasetDescriptor(
        key="NCES_IPEDS",
        owner="U.S. Department of Education / NCES",
        default_organization_type="UNIVERSITY",
        access_note="IPEDS institutional directory / complete data file.",
    ),
    "cms": DatasetDescriptor(
        key="CMS_HOSPITALS",
        owner="Centers for Medicare & Medicaid Services",
        default_organization_type="HOSPITAL",
        access_note="CMS Provider Data Catalog hospital organization data.",
    ),
    "irs": DatasetDescriptor(
        key="IRS_EO_BMF",
        owner="Internal Revenue Service",
        default_organization_type="NONPROFIT",
        access_note="IRS Exempt Organizations Business Master File / TEOS public bulk data.",
    ),
    "government": DatasetDescriptor(
        key="US_GOVERNMENT_DIRECTORY",
        owner="U.S. Government",
        default_organization_type="GOVERNMENT",
        access_note="Authoritative federal/state/local government organization directory input.",
    ),
}


def _text(value: Any) -> str | None:
    if value is None:
        return None
    result = " ".join(str(value).split()).strip()
    return result or None


def _domain_from_website(value: Any) -> str | None:
    raw = _text(value)
    if not raw:
        return None
    try:
        parsed = urlsplit(raw if "://" in raw else f"https://{raw}")
        return normalize_domain(parsed.hostname)
    except ValueError:
        return None


def _dataset_metadata(
    descriptor: DatasetDescriptor,
    *,
    source_identifier: str | None = None,
    source_url: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "dataset_key": descriptor.key,
        "dataset_owner": descriptor.owner,
        "dataset_source_identifier": source_identifier,
        "dataset_source_url": source_url or descriptor.source_url,
        "dataset_access_note": descriptor.access_note,
        **dict(extra or {}),
    }


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _records_from_jsonish(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [dict(item) for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("data", "results", "organizations", "institutions", "hospitals"):
        value = payload.get(key)
        if isinstance(value, list):
            return [dict(item) for item in value if isinstance(item, dict)]
    return [dict(payload)]


def parse_sec_company_payload(payload: Any) -> list[OrganizationRecord]:
    descriptor = DATASETS["sec"]
    rows: list[dict[str, Any]] = []
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        fields = [str(value) for value in payload.get("fields") or []]
        for raw in payload["data"]:
            if isinstance(raw, list):
                rows.append(dict(zip(fields, raw, strict=False)))
            elif isinstance(raw, dict):
                rows.append(dict(raw))
    elif isinstance(payload, dict):
        # SEC company_tickers.json uses numeric dictionary keys.
        rows = [dict(value) for value in payload.values() if isinstance(value, dict)]
    elif isinstance(payload, list):
        rows = [dict(value) for value in payload if isinstance(value, dict)]

    records: list[OrganizationRecord] = []
    for row in rows:
        name = _text(row.get("name") or row.get("title") or row.get("company_name"))
        cik = _text(row.get("cik") or row.get("cik_str") or row.get("CIK"))
        ticker = _text(row.get("ticker") or row.get("Ticker"))
        exchange = _text(row.get("exchange") or row.get("Exchange"))
        if not name or not cik:
            continue
        aliases = tuple(value for value in (ticker,) if value)
        records.append(
            OrganizationRecord(
                canonical_name=name,
                aliases=aliases,
                organization_type="PUBLIC_COMPANY",
                country_code="US",
                priority=75,
                dataset=descriptor.key,
                external_ids={"SEC_CIK": cik.zfill(10)},
                metadata=_dataset_metadata(
                    descriptor,
                    source_identifier=cik,
                    extra={"ticker": ticker, "exchange": exchange},
                ),
            )
        )
    return records


def parse_ipeds_rows(rows: Iterable[dict[str, Any]]) -> list[OrganizationRecord]:
    descriptor = DATASETS["ipeds"]
    records: list[OrganizationRecord] = []
    for row in rows:
        name = _text(row.get("INSTNM") or row.get("institution_name") or row.get("name"))
        unitid = _text(row.get("UNITID") or row.get("unitid") or row.get("id"))
        if not name or not unitid:
            continue
        website = row.get("WEBADDR") or row.get("website") or row.get("url")
        level = _text(row.get("ICLEVEL") or row.get("institution_level"))
        organization_type = "COLLEGE" if level in {"2", "3"} else "UNIVERSITY"
        records.append(
            OrganizationRecord(
                canonical_name=name,
                domain=_domain_from_website(website),
                organization_type=organization_type,
                country_code="US",
                state_region=_text(row.get("STABBR") or row.get("state")),
                priority=70,
                dataset=descriptor.key,
                external_ids={"IPEDS_UNITID": unitid},
                metadata=_dataset_metadata(
                    descriptor,
                    source_identifier=unitid,
                    extra={
                        "city": _text(row.get("CITY") or row.get("city")),
                        "institution_level": level,
                        "sector": _text(row.get("SECTOR") or row.get("sector")),
                    },
                ),
            )
        )
    return records


def parse_cms_hospital_rows(rows: Iterable[dict[str, Any]]) -> list[OrganizationRecord]:
    descriptor = DATASETS["cms"]
    records: list[OrganizationRecord] = []
    for row in rows:
        name = _text(
            row.get("Facility Name")
            or row.get("facility_name")
            or row.get("Hospital Name")
            or row.get("name")
        )
        provider_id = _text(
            row.get("Facility ID")
            or row.get("facility_id")
            or row.get("provider_id")
            or row.get("ccn")
        )
        if not name or not provider_id:
            continue
        records.append(
            OrganizationRecord(
                canonical_name=name,
                domain=_domain_from_website(
                    row.get("Website") or row.get("website") or row.get("hospital_url")
                ),
                organization_type="HOSPITAL",
                country_code="US",
                state_region=_text(row.get("State") or row.get("state")),
                priority=75,
                dataset=descriptor.key,
                external_ids={"CMS_PROVIDER_ID": provider_id},
                metadata=_dataset_metadata(
                    descriptor,
                    source_identifier=provider_id,
                    extra={
                        "city": _text(row.get("City/Town") or row.get("City") or row.get("city")),
                        "hospital_type": _text(row.get("Hospital Type") or row.get("hospital_type")),
                        "ownership": _text(row.get("Hospital Ownership") or row.get("ownership")),
                    },
                ),
            )
        )
    return records


def parse_irs_nonprofit_rows(rows: Iterable[dict[str, Any]]) -> list[OrganizationRecord]:
    descriptor = DATASETS["irs"]
    records: list[OrganizationRecord] = []
    for row in rows:
        name = _text(row.get("NAME") or row.get("name") or row.get("organization_name"))
        ein = _text(row.get("EIN") or row.get("ein"))
        if not name or not ein:
            continue
        records.append(
            OrganizationRecord(
                canonical_name=name,
                organization_type="NONPROFIT",
                country_code="US",
                state_region=_text(row.get("STATE") or row.get("state")),
                priority=35,
                dataset=descriptor.key,
                external_ids={"IRS_EIN": ein.replace("-", "")},
                metadata=_dataset_metadata(
                    descriptor,
                    source_identifier=ein,
                    extra={
                        "city": _text(row.get("CITY") or row.get("city")),
                        "ntee_code": _text(row.get("NTEE_CD") or row.get("ntee_code")),
                        "subsection": _text(row.get("SUBSECTION") or row.get("subsection")),
                        "asset_code": _text(row.get("ASSET_CD") or row.get("asset_code")),
                        "income_code": _text(row.get("INCOME_CD") or row.get("income_code")),
                    },
                ),
            )
        )
    return records


def parse_government_rows(rows: Iterable[dict[str, Any]]) -> list[OrganizationRecord]:
    descriptor = DATASETS["government"]
    records: list[OrganizationRecord] = []
    for row in rows:
        name = _text(row.get("agency_name") or row.get("name") or row.get("organization_name"))
        if not name:
            continue
        level = (_text(row.get("government_level") or row.get("level")) or "FEDERAL").upper()
        organization_type = {
            "FEDERAL": "FEDERAL_AGENCY",
            "STATE": "STATE_AGENCY",
            "LOCAL": "LOCAL_GOVERNMENT",
        }.get(level, "GOVERNMENT")
        external_id = _text(row.get("agency_id") or row.get("external_id") or row.get("id"))
        records.append(
            OrganizationRecord(
                canonical_name=name,
                domain=_domain_from_website(row.get("domain") or row.get("website")),
                organization_type=organization_type,
                country_code=(_text(row.get("country_code")) or "US").upper(),
                state_region=_text(row.get("state") or row.get("state_region")),
                priority=80 if level == "FEDERAL" else 65,
                dataset=descriptor.key,
                external_ids={"GOVERNMENT_AGENCY_ID": external_id} if external_id else {},
                metadata=_dataset_metadata(
                    descriptor,
                    source_identifier=external_id,
                    extra={"government_level": level},
                ),
            )
        )
    return records


def load_dataset_records(path: str | Path, *, dataset_type: str) -> list[OrganizationRecord]:
    source = Path(path)
    key = dataset_type.casefold().strip()
    if key not in DATASETS:
        raise ValueError(f"Unsupported dataset_type: {dataset_type}")

    suffix = source.suffix.casefold()
    if suffix == ".csv":
        rows = _read_csv(source)
        if key == "ipeds":
            return parse_ipeds_rows(rows)
        if key == "cms":
            return parse_cms_hospital_rows(rows)
        if key == "irs":
            return parse_irs_nonprofit_rows(rows)
        if key == "government":
            return parse_government_rows(rows)
        # SEC can also be represented as a normalized CSV export.
        return parse_sec_company_payload(rows)

    if suffix in {".json", ".jsonl"}:
        if suffix == ".jsonl":
            payload = [
                json.loads(line)
                for line in source.read_text(encoding="utf-8-sig").splitlines()
                if line.strip()
            ]
        else:
            payload = _read_json(source)
        if key == "sec":
            return parse_sec_company_payload(payload)
        rows = _records_from_jsonish(payload)
        if key == "ipeds":
            return parse_ipeds_rows(rows)
        if key == "cms":
            return parse_cms_hospital_rows(rows)
        if key == "irs":
            return parse_irs_nonprofit_rows(rows)
        if key == "government":
            return parse_government_rows(rows)

    raise ValueError("Authoritative dataset imports support CSV, JSON and JSONL")


def load_dataset_bytes(content: bytes, *, dataset_type: str, format_hint: str) -> list[OrganizationRecord]:
    key = dataset_type.casefold().strip()
    if key not in DATASETS:
        raise ValueError(f"Unsupported dataset_type: {dataset_type}")
    hint = format_hint.casefold().lstrip(".")
    if hint == "csv":
        rows = list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
        if key == "ipeds":
            return parse_ipeds_rows(rows)
        if key == "cms":
            return parse_cms_hospital_rows(rows)
        if key == "irs":
            return parse_irs_nonprofit_rows(rows)
        if key == "government":
            return parse_government_rows(rows)
        return parse_sec_company_payload(rows)
    if hint in {"json", "jsonl"}:
        payload = (
            [json.loads(line) for line in content.decode("utf-8-sig").splitlines() if line.strip()]
            if hint == "jsonl"
            else json.loads(content.decode("utf-8-sig"))
        )
        if key == "sec":
            return parse_sec_company_payload(payload)
        rows = _records_from_jsonish(payload)
        if key == "ipeds":
            return parse_ipeds_rows(rows)
        if key == "cms":
            return parse_cms_hospital_rows(rows)
        if key == "irs":
            return parse_irs_nonprofit_rows(rows)
        if key == "government":
            return parse_government_rows(rows)
    raise ValueError("Unsupported authoritative dataset payload format")
