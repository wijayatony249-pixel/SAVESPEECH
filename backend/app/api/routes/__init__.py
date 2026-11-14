"""Routes package"""
from app.api.routes import health, auth, analyze, jobs, results, history

__all__ = ["health", "auth", "analyze", "jobs", "results", "history"]
