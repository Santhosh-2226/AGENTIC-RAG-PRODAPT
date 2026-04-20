"""
ingest/ingest_docs.py

Build search index from OCRed PDFs.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.search_docs import ingest_documents


def main():
    print("=" * 60)
    print("IPL OCRed Document Ingestion")
    print("=" * 60)

    try:
        ok = ingest_documents()
        if not ok:
            print("\nIngestion failed.")
            sys.exit(1)

        print("\nIngestion complete.")
        print("Now test retrieval:")
        print("  python tools/search_docs.py")
    except Exception as e:
        print(f"\nERROR during ingestion: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()