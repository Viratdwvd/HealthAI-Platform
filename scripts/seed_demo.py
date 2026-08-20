#!/usr/bin/env python3
"""
seed_demo.py
------------
Seeds the platform with demo healthcare data so you can start querying
immediately after docker compose up.

Usage:
    python scripts/seed_demo.py --base-url http://localhost:8000
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import io
import json
import sys
import time
from datetime import date, timedelta
from typing import Any

import httpx


# ─── Sample data generators ───────────────────────────────────────────────────

def _patient_csv() -> bytes:
    header = "patient_id,age,gender,diagnosis,admission_date,discharge_date,los_days,readmitted"
    rows = [
        "P001,67,M,Heart Failure,2024-01-05,2024-01-12,7,No",
        "P002,45,F,Type 2 Diabetes,2024-01-06,2024-01-09,3,No",
        "P003,72,M,COPD,2024-01-07,2024-01-15,8,Yes",
        "P004,58,F,Hypertension,2024-01-08,2024-01-10,2,No",
        "P005,81,M,Pneumonia,2024-01-09,2024-01-20,11,Yes",
        "P006,34,F,Appendicitis,2024-01-10,2024-01-13,3,No",
        "P007,63,M,Atrial Fibrillation,2024-01-11,2024-01-16,5,No",
        "P008,55,F,Breast Cancer,2024-01-12,2024-01-18,6,No",
        "P009,78,M,Hip Fracture,2024-01-13,2024-01-25,12,Yes",
        "P010,44,F,Migraine,2024-01-14,2024-01-15,1,No",
        "P011,69,M,Stroke,2024-01-15,2024-01-28,13,Yes",
        "P012,52,F,Kidney Stones,2024-01-16,2024-01-18,2,No",
        "P013,76,M,Prostate Cancer,2024-01-17,2024-01-24,7,No",
        "P014,41,F,Asthma,2024-01-18,2024-01-20,2,No",
        "P015,88,M,Dementia,2024-01-19,2024-02-02,14,Yes",
        "P016,60,F,Lupus,2024-01-20,2024-01-25,5,No",
        "P017,73,M,Parkinson Disease,2024-01-21,2024-01-29,8,No",
        "P018,49,F,Rheumatoid Arthritis,2024-01-22,2024-01-26,4,No",
        "P019,66,M,Colorectal Cancer,2024-01-23,2024-01-31,8,No",
        "P020,57,F,Osteoporosis,2024-01-24,2024-01-27,3,No",
    ]
    return ("\n".join([header] + rows)).encode()


def _admissions_ts_csv() -> bytes:
    """Daily admissions time-series for forecasting demo."""
    header = "date,admissions,icu_count,er_visits"
    start  = date(2023, 1, 1)
    rows   = []
    import math, random
    random.seed(42)
    for i in range(365):
        d       = start + timedelta(days=i)
        base    = 45 + 10 * math.sin(2 * math.pi * i / 365)
        weekend = -8 if d.weekday() >= 5 else 0
        noise   = random.gauss(0, 3)
        adm     = max(10, int(base + weekend + noise))
        icu     = max(2, int(adm * 0.15 + random.gauss(0, 1)))
        er      = max(5, int(adm * 0.6  + random.gauss(0, 4)))
        rows.append(f"{d.isoformat()},{adm},{icu},{er}")
    return ("\n".join([header] + rows)).encode()


def _medications_csv() -> bytes:
    header = "patient_id,medication,dose_mg,frequency,start_date,prescriber"
    rows = [
        "P001,Furosemide,40,BID,2024-01-05,Dr. Chen",
        "P001,Lisinopril,10,QD,2024-01-05,Dr. Chen",
        "P002,Metformin,500,BID,2024-01-06,Dr. Patel",
        "P002,Empagliflozin,10,QD,2024-01-06,Dr. Patel",
        "P003,Salbutamol,200,PRN,2024-01-07,Dr. Smith",
        "P003,Fluticasone,250,BID,2024-01-07,Dr. Smith",
        "P004,Amlodipine,5,QD,2024-01-08,Dr. Johnson",
        "P007,Warfarin,5,QD,2024-01-11,Dr. Brown",
        "P007,Metoprolol,50,BID,2024-01-11,Dr. Brown",
        "P011,Aspirin,100,QD,2024-01-15,Dr. Wilson",
        "P011,Clopidogrel,75,QD,2024-01-15,Dr. Wilson",
    ]
    return ("\n".join([header] + rows)).encode()


def _clinical_notes_pdf_placeholder() -> bytes:
    """
    Returns a minimal valid PDF with synthetic clinical note text.
    In production this would be a real PDF; here we create one programmatically.
    """
    content = b"""\
%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]
  /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj << /Length 850 >>
stream
BT
/F1 12 Tf
50 750 Td
(CLINICAL DISCHARGE SUMMARY) Tj
0 -20 Td (Patient: John Doe   DOB: 1956-03-14   MRN: P001) Tj
0 -20 Td (Admission: 2024-01-05   Discharge: 2024-01-12) Tj
0 -20 Td (Primary Diagnosis: Congestive Heart Failure NYHA Class III) Tj
0 -20 Td () Tj
0 -20 Td (PRESENTING COMPLAINT:) Tj
0 -20 Td (Patient presented with progressive dyspnea on exertion, bilateral) Tj
0 -20 Td (ankle oedema and orthopnoea. BNP was 1420 pg/mL.) Tj
0 -20 Td () Tj
0 -20 Td (INVESTIGATIONS:) Tj
0 -20 Td (ECG: Sinus tachycardia, no acute ischaemic changes.) Tj
0 -20 Td (Echo: EF 32%, severe LV dysfunction, dilated LV.) Tj
0 -20 Td (CXR: Cardiomegaly with bilateral pulmonary oedema.) Tj
0 -20 Td () Tj
0 -20 Td (TREATMENT:) Tj
0 -20 Td (IV Furosemide 80mg BD for 48h, then oral 40mg BD.) Tj
0 -20 Td (Lisinopril 10mg QD commenced. Fluid restriction 1.5L/day.) Tj
0 -20 Td () Tj
0 -20 Td (DISCHARGE PLAN:) Tj
0 -20 Td (Follow up with cardiology in 2 weeks.) Tj
0 -20 Td (Daily weights, fluid diary. Seek help if weight gain >2kg in 2 days.) Tj
ET
endstream
endobj
5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj
xref
0 6
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000266 00000 n
0000001168 00000 n
trailer << /Size 6 /Root 1 0 R >>
startxref
1251
%%EOF"""
    return content


# ─── API helpers ──────────────────────────────────────────────────────────────

async def get_token(client: httpx.AsyncClient, base: str) -> str:
    r = await client.post(
        f"{base}/auth/token",
        json={"username": "demo_user", "password": "demo", "tenant_id": "tenant-demo"},
    )
    r.raise_for_status()
    return r.json()["access_token"]


async def upload_file(
    client:    httpx.AsyncClient,
    base:      str,
    token:     str,
    name:      str,
    file_type: str,
    content:   bytes,
    tags:      list[str],
) -> dict[str, Any]:
    payload = {
        "file_name":   name,
        "file_type":   file_type,
        "content_b64": base64.b64encode(content).decode(),
        "tenant_id":   "tenant-demo",
        "user_id":     "demo_user",
        "tags":        tags,
        "metadata":    {"seeded": True},
    }
    r = await client.post(
        f"{base}/api/v1/ingest",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    r.raise_for_status()
    return r.json()


async def poll_job(
    client: httpx.AsyncClient,
    base:   str,
    token:  str,
    job_id: str,
    max_s:  int = 60,
) -> dict[str, Any]:
    for _ in range(max_s * 2):
        r = await client.get(
            f"{base}/api/v1/ingest/{job_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        r.raise_for_status()
        data = r.json()
        if data["status"] in ("done", "failed"):
            return data
        await asyncio.sleep(0.5)
    return {"status": "timeout"}


async def send_query(
    client: httpx.AsyncClient,
    base:   str,
    token:  str,
    query:  str,
) -> dict[str, Any]:
    r = await client.post(
        f"{base}/api/v1/query",
        json={"query": query, "tenant_id": "tenant-demo", "user_id": "demo_user"},
        headers={"Authorization": f"Bearer {token}"},
    )
    r.raise_for_status()
    return r.json()


# ─── Main ─────────────────────────────────────────────────────────────────────

async def main(base_url: str) -> None:
    print(f"\n🏥  HealthAI Platform – Demo Seeder")
    print(f"    Target: {base_url}\n")

    async with httpx.AsyncClient(timeout=60) as client:

        # 1. Auth
        print("🔐  Authenticating …")
        try:
            token = await get_token(client, base_url)
            print("    ✅  Token acquired\n")
        except Exception as e:
            print(f"    ❌  Auth failed: {e}")
            print("    Is the platform running? Try: docker compose up -d")
            sys.exit(1)

        # 2. Upload files
        uploads = [
            ("patients.csv",            "csv", _patient_csv(),              ["patients", "demographics"]),
            ("daily_admissions.csv",    "csv", _admissions_ts_csv(),        ["time-series", "admissions"]),
            ("medications.csv",         "csv", _medications_csv(),           ["medications"]),
            ("discharge_summary.pdf",   "pdf", _clinical_notes_pdf_placeholder(), ["clinical-notes"]),
        ]

        job_ids: list[str] = []
        for name, ftype, content, tags in uploads:
            size_kb = len(content) / 1024
            print(f"📤  Uploading {name} ({size_kb:.1f} KB) …")
            try:
                job = await upload_file(client, base_url, token, name, ftype, content, tags)
                job_ids.append(job["job_id"])
                print(f"    Job ID: {job['job_id']}")
            except Exception as e:
                print(f"    ⚠️  Upload failed: {e}")

        # 3. Poll jobs
        print("\n⏳  Waiting for ingestion jobs …")
        for job_id in job_ids:
            result = await poll_job(client, base_url, token, job_id)
            status = result.get("status", "unknown")
            chunks = result.get("chunks", 0)
            icon   = "✅" if status == "done" else "❌"
            print(f"    {icon}  Job {job_id[:8]}… → {status} ({chunks} chunks)")

        # 4. Demo queries
        demo_queries = [
            "What are the most common diagnoses in the patient dataset?",
            "Which patients were readmitted?",
            "What medications are prescribed for heart failure patients?",
        ]

        print("\n💬  Running demo queries …\n")
        for q in demo_queries:
            print(f"  Q: {q}")
            try:
                resp = await send_query(client, base_url, token, q)
                answer = resp.get("answer", "No answer")
                conf   = resp.get("confidence", 0)
                srcs   = len(resp.get("sources", []))
                print(f"  A: {answer[:200]}{'…' if len(answer) > 200 else ''}")
                print(f"     [confidence={conf:.2f}  sources={srcs}]\n")
            except Exception as e:
                print(f"  ⚠️  Query failed: {e}\n")

    print("🎉  Seeding complete! Open http://localhost:3000 to explore.\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed HealthAI platform with demo data")
    parser.add_argument("--base-url", default="http://localhost:8000", help="API Gateway URL")
    args = parser.parse_args()
    asyncio.run(main(args.base_url))
