"""Tests for IEMCRP Real Constrained Database Pool and Semaphore Contention (PRD-02 §1.1)."""

import pytest
import time
from backend.portals.iemcrp_app import DB_POOL, IEMCRP_INFRA_STATE


def test_iemcrp_pool_initial_capacity():
    assert DB_POOL.max_connections == 50
    assert DB_POOL.available_connections == 50
    assert DB_POOL.active_connections == 0


def test_iemcrp_connection_acquisition_and_release():
    conn = DB_POOL.acquire_connection(timeout=1.0)
    assert conn is not None
    assert DB_POOL.active_connections == 1
    assert DB_POOL.available_connections == 49

    DB_POOL.release_connection(conn)
    assert DB_POOL.active_connections == 0
    assert DB_POOL.available_connections == 50


def test_iemcrp_fault_pool_exhaustion():
    # Artificially lock 48 connections
    DB_POOL.set_fault_pool_exhaustion(True)
    assert DB_POOL.active_connections >= 48
    assert DB_POOL.available_connections <= 2

    # Reset
    DB_POOL.set_fault_pool_exhaustion(False)
    assert DB_POOL.active_connections == 0
    assert DB_POOL.available_connections == 50


def test_iemcrp_connection_starvation_timeout():
    # Exhaust all 50 connections
    conns = []
    for _ in range(50):
        c = DB_POOL.acquire_connection(timeout=0.2)
        if c:
            conns.append(c)
    assert len(conns) == 50
    assert DB_POOL.available_connections == 0

    # Connection 51 should fail with timeout
    t0 = time.time()
    conn_51 = DB_POOL.acquire_connection(timeout=0.1)
    assert not conn_51  # Starvation
    assert time.time() - t0 >= 0.08

    # Clean up
    for c in conns:
        DB_POOL.release_connection(c)
    assert DB_POOL.available_connections == 50
