
import sys
import os

print("Verifying imports...")

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    import crawler.sec_crawler
    print("Crawler: OK")
except Exception as e:
    print(f"Crawler: FAILED - {e}")

try:
    import crawler.dart_crawler
    print("DART Crawler: OK")
except Exception as e:
    print(f"DART Crawler: FAILED - {e}")

try:
    import parser.html_parser
    print("Parser: OK")
except Exception as e:
    print(f"Parser: FAILED - {e}")

try:
    import extractor.license_extractor
    print("Extractor: OK")
except Exception as e:
    print(f"Extractor: FAILED - {e}")

try:
    import database.load_data
    print("Database Loader: OK")
except Exception as e:
    print(f"Database Loader: FAILED - {e}")

try:
    import valuation.valuator
    print("Valuation: OK")
except Exception as e:
    print(f"Valuation: FAILED - {e}")

try:
    import orchestrator.run_pipeline
    print("Orchestrator: OK")
except Exception as e:
    print(f"Orchestrator: FAILED - {e}")

try:
    import orchestrator.run_dart_pipeline
    print("DART Orchestrator: OK")
except Exception as e:
    print(f"DART Orchestrator: FAILED - {e}")

print("Verification complete.")
