# High-Concurrency Virtual User (VU) Swarm Guide

## Overview
To load test the university portal with 10,000 concurrent students without requiring physical client devices, we utilize an asynchronous virtual user (VU) swarming architecture.

## Locust Load Test Definition
```python
from locust import HttpUser, task, between
import random


class StudentUser(HttpUser):
    wait_time = between(1.5, 4.0)

    def on_start(self):
        self.enrollment = f"2024CS{random.randint(1000, 1250)}"
        self.headers = {"X-Quantum-Key": "STU-QKEY-3B8A7F1C9E20"}

    @task(3)
    def query_results(self):
        self.client.get(f"/api/results/{self.enrollment}", headers=self.headers)
```

## Running the Swarm
```bash
locust -f load_test.py --headless -u 10000 -r 250 --run-time 10m --host http://localhost:8501
```
