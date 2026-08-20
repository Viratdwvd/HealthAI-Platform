"""
Load Test – HealthAI Platform
------------------------------
Simulates realistic multi-user traffic against the API Gateway.

Prerequisites:
    pip install locust

Run:
    # Local (against docker compose)
    locust -f scripts/load_test.py --host http://localhost:8000 \
           --users 50 --spawn-rate 5 --run-time 2m --headless

    # Open web UI
    locust -f scripts/load_test.py --host http://localhost:8000
    # → open http://localhost:8089
"""

from __future__ import annotations

import base64
import json
import os
import random
from typing import Any

from locust import HttpUser, TaskSet, between, events, task


# ─── Shared demo data ─────────────────────────────────────────────────────────

_DEMO_CSV_B64 = base64.b64encode(
    b"patient_id,age,diagnosis,admission_date\n"
    b"P001,67,Heart Failure,2024-01-05\n"
    b"P002,45,Diabetes,2024-01-06\n"
    b"P003,72,COPD,2024-01-07\n"
).decode()

_SAMPLE_QUERIES = [
    "What are the most common diagnoses?",
    "Which patients were readmitted within 30 days?",
    "Summarise the medications prescribed for heart failure.",
    "What is the average length of stay?",
    "Are there any patients with both diabetes and hypertension?",
    "What does the clinical note say about patient P001?",
    "Show me ECG findings from the discharge summary.",
    "List all patients admitted in January 2024.",
]

_TOKEN: str = ""


# ─── Auth helper ──────────────────────────────────────────────────────────────

def _get_token(client: Any, host: str) -> str:
    resp = client.post(
        "/auth/token",
        json={"username": "load_test_user", "password": "demo", "tenant_id": "tenant-demo"},
        name="/auth/token",
    )
    if resp.status_code == 200:
        return resp.json()["access_token"]
    return ""


# ─── Task sets ────────────────────────────────────────────────────────────────

class QueryTasks(TaskSet):
    """Simulates a knowledge-worker making queries."""

    @task(8)
    def query_platform(self):
        q = random.choice(_SAMPLE_QUERIES)
        self.client.post(
            "/api/v1/query",
            json={"query": q, "tenant_id": "tenant-demo", "user_id": "load_test_user"},
            headers={"Authorization": f"Bearer {_TOKEN}"},
            name="/api/v1/query",
        )

    @task(2)
    def get_health(self):
        self.client.get("/health", name="/health")

    @task(1)
    def run_stats(self):
        demo_data = [
            {"ds": f"2024-{m:02d}-01", "y": 100 + m * 5 + random.randint(-5, 5)}
            for m in range(1, 13)
        ]
        self.client.post(
            "/api/v1/analytics",
            json={
                "tenant_id": "tenant-demo",
                "dataset_id": "load-test",
                "operation": "stats",
                "params": {"data": demo_data},
            },
            headers={"Authorization": f"Bearer {_TOKEN}"},
            name="/api/v1/analytics [stats]",
        )

    @task(1)
    def run_forecast(self):
        demo_data = [
            {"ds": f"2024-{m:02d}-01", "y": 40 + m * 2 + random.randint(-3, 3)}
            for m in range(1, 13)
        ]
        self.client.post(
            "/api/v1/analytics",
            json={
                "tenant_id": "tenant-demo",
                "dataset_id": "load-test",
                "operation": "forecast",
                "params": {"data": demo_data, "horizon": 30},
            },
            headers={"Authorization": f"Bearer {_TOKEN}"},
            name="/api/v1/analytics [forecast]",
        )


class IngestionTasks(TaskSet):
    """Simulates a data-engineer uploading files."""

    @task(5)
    def upload_csv(self):
        resp = self.client.post(
            "/api/v1/ingest",
            json={
                "file_name":   f"load_test_{random.randint(1000, 9999)}.csv",
                "file_type":   "csv",
                "content_b64": _DEMO_CSV_B64,
                "tenant_id":   "tenant-demo",
                "user_id":     "load_test_user",
                "tags":        ["load-test"],
                "metadata":    {},
            },
            headers={"Authorization": f"Bearer {_TOKEN}"},
            name="/api/v1/ingest [csv]",
        )
        if resp.status_code == 202:
            job_id = resp.json().get("job_id")
            if job_id:
                # Poll status once
                self.client.get(
                    f"/api/v1/ingest/{job_id}",
                    headers={"Authorization": f"Bearer {_TOKEN}"},
                    name="/api/v1/ingest/{job_id}",
                )

    @task(2)
    def check_health(self):
        self.client.get("/health", name="/health")


class KnowledgeTasks(TaskSet):
    """Simulates clinical staff querying the knowledge base."""

    _TERMS = ["chest pain", "HbA1c", "blood pressure", "arrhythmia", "drug interaction"]

    @task
    def lookup_knowledge(self):
        self.client.post(
            "/api/v1/knowledge",
            json={
                "query":     random.choice(self._TERMS),
                "tenant_id": "tenant-demo",
            },
            headers={"Authorization": f"Bearer {_TOKEN}"},
            name="/api/v1/knowledge",
        )


# ─── User classes ─────────────────────────────────────────────────────────────

class AnalystUser(HttpUser):
    """Power user making frequent queries."""
    tasks       = [QueryTasks]
    wait_time   = between(1, 4)
    weight      = 60

    def on_start(self):
        global _TOKEN
        _TOKEN = _get_token(self.client, self.host)


class DataEngineerUser(HttpUser):
    """Less frequent; uploads data and checks jobs."""
    tasks       = [IngestionTasks]
    wait_time   = between(5, 15)
    weight      = 20

    def on_start(self):
        global _TOKEN
        if not _TOKEN:
            _TOKEN = _get_token(self.client, self.host)


class ClinicalUser(HttpUser):
    """Clinical staff using the knowledge base."""
    tasks       = [KnowledgeTasks]
    wait_time   = between(3, 10)
    weight      = 20

    def on_start(self):
        global _TOKEN
        if not _TOKEN:
            _TOKEN = _get_token(self.client, self.host)


# ─── Event hooks ──────────────────────────────────────────────────────────────

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print("\n🚀 HealthAI Load Test Starting")
    print(f"   Host: {environment.host}")
    print(f"   Users: {environment.runner.target_user_count if environment.runner else '?'}\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    stats = environment.stats.total
    print(f"\n📊 Load Test Complete")
    print(f"   Requests:    {stats.num_requests}")
    print(f"   Failures:    {stats.num_failures}")
    print(f"   Median RT:   {stats.median_response_time}ms")
    print(f"   P99 RT:      {stats.get_response_time_percentile(0.99)}ms")
    print(f"   RPS:         {stats.current_rps:.1f}\n")
