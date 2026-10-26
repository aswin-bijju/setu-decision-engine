"""Start Setu: python run.py [--port 8000] [--reset]"""
import argparse

from server import serve

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Setu commercial decision engine")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--db", help="SQLite file path (default: data/setu.db)")
    p.add_argument("--reset", action="store_true", help="Reload the EU-India demo data")
    a = p.parse_args()
    serve(a.host, a.port, a.db, a.reset)
