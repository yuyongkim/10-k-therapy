"""
RAG Engine: Retrieval-Augmented Generation for License Intelligence

Uses ChromaDB to index existing extracted license agreements and provide
relevant context when processing new filings.

Data sources:
1. SQLite sec_agreements table (existing extraction results)
2. DART unified schema JSON files
3. Litigation royalty CSV data
"""

import os
import json
import csv
import sqlite3
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Default embedding function uses sentence-transformers
COLLECTION_NAME = "license_agreements"
DART_COLLECTION = "dart_filings"
LITIGATION_COLLECTION = "litigation_royalties"


class RAGEngine:
    """Vector-based contextual retrieval for license extraction."""

    def __init__(self, persist_dir: str = None, db_path: str = None):
        project_root = Path(__file__).parent.parent
        self.persist_dir = persist_dir or str(project_root / "data" / "chromadb")
        self.db_path = db_path or str(
            project_root / "data" / "processed" / "sec_dart_analytics.db"
        )
        self.client = None
        self.embedding_fn = None
        self._initialized = False

    def _init_chroma(self):
        """Lazy initialization of ChromaDB client."""
        if self._initialized:
            return

        try:
            import chromadb
            from chromadb.config import Settings

            os.makedirs(self.persist_dir, exist_ok=True)
            self.client = chromadb.PersistentClient(
                path=self.persist_dir,
                settings=Settings(anonymized_telemetry=False),
            )

            # Try to use sentence-transformers for better embeddings
            try:
                from chromadb.utils.embedding_functions import (
                    SentenceTransformerEmbeddingFunction,
                )
                self.embedding_fn = SentenceTransformerEmbeddingFunction(
                    model_name="all-MiniLM-L6-v2"
                )
            except ImportError:
                logger.info(
                    "sentence-transformers not available, using ChromaDB default embeddings"
                )
                self.embedding_fn = None

            self._initialized = True
            logger.info("ChromaDB initialized at %s", self.persist_dir)
        except ImportError:
            logger.error(
                "chromadb not installed. Run: pip install chromadb"
            )
            raise

    def _get_collection(self, name: str):
        self._init_chroma()
        kwargs = {"name": name}
        if self.embedding_fn:
            kwargs["embedding_function"] = self.embedding_fn
        return self.client.get_or_create_collection(**kwargs)

    # ----------------------------------------------------------------
    # Indexing: Load existing data into vector store
    # ----------------------------------------------------------------

    def index_from_sqlite(self, batch_size: int = 100) -> int:
        """Index SEC agreements from SQLite into ChromaDB."""
        self._init_chroma()
        collection = self._get_collection(COLLECTION_NAME)

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            """SELECT agreement_id, company, cik, ticker, filing_type, filing_year,
                      licensor_name, licensee_name, tech_name, tech_category,
                      confidence, royalty_rate, royalty_unit, upfront_amount,
                      territory, reasoning
               FROM sec_agreements"""
        )

        count = 0
        batch_ids = []
        batch_docs = []
        batch_metas = []

        for row in cursor:
            row_dict = dict(row)
            doc_id = f"sec_{row_dict['agreement_id']}"

            # Build document text for embedding
            doc_text = self._build_agreement_text(row_dict)

            # Metadata for filtering
            meta = {
                "source": "sec",
                "company": row_dict.get("company") or "",
                "cik": row_dict.get("cik") or "",
                "tech_category": row_dict.get("tech_category") or "",
                "filing_year": row_dict.get("filing_year") or 0,
                "confidence": row_dict.get("confidence") or 0.0,
                "has_royalty": 1 if row_dict.get("royalty_rate") else 0,
            }
            # ChromaDB metadata values must be str, int, float, or bool
            meta = {k: v for k, v in meta.items() if v is not None}

            batch_ids.append(doc_id)
            batch_docs.append(doc_text)
            batch_metas.append(meta)
            count += 1

            if len(batch_ids) >= batch_size:
                collection.upsert(ids=batch_ids, documents=batch_docs, metadatas=batch_metas)
                batch_ids, batch_docs, batch_metas = [], [], []

        if batch_ids:
            collection.upsert(ids=batch_ids, documents=batch_docs, metadatas=batch_metas)

        conn.close()
        logger.info("Indexed %d SEC agreements into ChromaDB", count)
        return count

    def index_dart_sections(self, batch_size: int = 100) -> int:
        """Index high-signal DART sections from SQLite."""
        self._init_chroma()
        collection = self._get_collection(DART_COLLECTION)

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            """SELECT ds.row_id, ds.section_key, ds.sec_label, ds.dart_label,
                      ds.candidate_score, ds.plain_text, ds.preview,
                      df.company_name, df.company_identifier
               FROM dart_sections ds
               JOIN dart_filings df ON ds.filing_id = df.filing_id
               WHERE ds.candidate_score >= 3"""
        )

        count = 0
        batch_ids, batch_docs, batch_metas = [], [], []

        for row in cursor:
            row_dict = dict(row)
            doc_id = f"dart_{row_dict['row_id']}"
            text = row_dict.get("plain_text") or row_dict.get("preview") or ""
            if not text.strip():
                continue

            # Truncate very long sections for embedding
            if len(text) > 5000:
                text = text[:5000]

            meta = {
                "source": "dart",
                "company": row_dict.get("company_name") or "",
                "section": row_dict.get("sec_label") or row_dict.get("dart_label") or "",
                "score": row_dict.get("candidate_score") or 0,
            }

            batch_ids.append(doc_id)
            batch_docs.append(text)
            batch_metas.append(meta)
            count += 1

            if len(batch_ids) >= batch_size:
                collection.upsert(ids=batch_ids, documents=batch_docs, metadatas=batch_metas)
                batch_ids, batch_docs, batch_metas = [], [], []

        if batch_ids:
            collection.upsert(ids=batch_ids, documents=batch_docs, metadatas=batch_metas)

        conn.close()
        logger.info("Indexed %d DART sections into ChromaDB", count)
        return count

    def index_litigation_csv(self, csv_path: str = None) -> int:
        """Index litigation royalty data from CSV."""
        self._init_chroma()
        collection = self._get_collection(LITIGATION_COLLECTION)

        if csv_path is None:
            # Find latest litigation CSV
            exports_dir = Path(self.db_path).parent.parent / "exports"
            csvs = sorted(exports_dir.glob("litigation_royalties_*.csv"))
            if not csvs:
                logger.info("No litigation CSV files found")
                return 0
            csv_path = str(csvs[-1])

        count = 0
        batch_ids, batch_docs, batch_metas = [], [], []

        try:
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for i, row in enumerate(reader):
                    doc_id = f"lit_{i}"
                    # Build searchable text from CSV columns
                    parts = [
                        row.get("case_name", ""),
                        row.get("technology", ""),
                        row.get("industry", ""),
                        f"Royalty rate: {row.get('royalty_rate', '')}",
                        row.get("reasoning", ""),
                    ]
                    doc_text = " | ".join(p for p in parts if p)

                    meta = {
                        "source": "litigation",
                        "case_name": (row.get("case_name") or "")[:200],
                    }

                    batch_ids.append(doc_id)
                    batch_docs.append(doc_text)
                    batch_metas.append(meta)
                    count += 1

                    if len(batch_ids) >= 100:
                        collection.upsert(ids=batch_ids, documents=batch_docs, metadatas=batch_metas)
                        batch_ids, batch_docs, batch_metas = [], [], []

            if batch_ids:
                collection.upsert(ids=batch_ids, documents=batch_docs, metadatas=batch_metas)
        except Exception as e:
            logger.error("Failed to index litigation CSV: %s", e)

        logger.info("Indexed %d litigation records into ChromaDB", count)
        return count

    def index_all(self) -> Dict[str, int]:
        """Index all data sources."""
        results = {}
        results["sec_agreements"] = self.index_from_sqlite()
        results["dart_sections"] = self.index_dart_sections()
        results["litigation"] = self.index_litigation_csv()
        logger.info("Full index complete: %s", results)
        return results

    # ----------------------------------------------------------------
    # Retrieval: Find similar documents for context augmentation
    # ----------------------------------------------------------------

    def search_similar(
        self,
        query_text: str,
        n_results: int = 5,
        collection_name: str = COLLECTION_NAME,
        where_filter: Dict = None,
    ) -> List[Dict[str, Any]]:
        """Search for similar documents in the vector store."""
        try:
            self._init_chroma()
            collection = self._get_collection(collection_name)

            if collection.count() == 0:
                return []

            kwargs = {
                "query_texts": [query_text],
                "n_results": min(n_results, collection.count()),
            }
            if where_filter:
                kwargs["where"] = where_filter

            results = collection.query(**kwargs)

            docs = []
            for i in range(len(results["ids"][0])):
                docs.append({
                    "id": results["ids"][0][i],
                    "document": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else None,
                })
            return docs
        except Exception as e:
            logger.error("RAG search failed: %s", e)
            return []

    def get_context_for_extraction(
        self,
        text: str,
        tech_category: str = None,
        n_results: int = 3,
    ) -> str:
        """Build RAG context string for LLM prompt augmentation."""
        # Search across all collections
        sec_results = self.search_similar(
            text,
            n_results=n_results,
            collection_name=COLLECTION_NAME,
            where_filter={"tech_category": tech_category} if tech_category else None,
        )
        dart_results = self.search_similar(
            text, n_results=2, collection_name=DART_COLLECTION,
        )
        lit_results = self.search_similar(
            text, n_results=2, collection_name=LITIGATION_COLLECTION,
        )

        context_parts = []

        if sec_results:
            context_parts.append("## Similar SEC License Agreements (Reference)")
            for doc in sec_results[:3]:
                context_parts.append(f"- {doc['document'][:500]}")

        if dart_results:
            context_parts.append("\n## Related DART Disclosures")
            for doc in dart_results[:2]:
                context_parts.append(f"- {doc['document'][:300]}")

        if lit_results:
            context_parts.append("\n## Related Litigation Royalty Data")
            for doc in lit_results[:2]:
                context_parts.append(f"- {doc['document'][:300]}")

        return "\n".join(context_parts) if context_parts else ""

    def add_document(
        self,
        doc_id: str,
        text: str,
        metadata: Dict[str, Any],
        collection_name: str = COLLECTION_NAME,
    ):
        """Add a single document to the vector store (for incremental updates)."""
        try:
            self._init_chroma()
            collection = self._get_collection(collection_name)
            # Ensure metadata values are compatible types
            clean_meta = {
                k: v for k, v in metadata.items()
                if isinstance(v, (str, int, float, bool))
            }
            collection.upsert(ids=[doc_id], documents=[text], metadatas=[clean_meta])
        except Exception as e:
            logger.error("Failed to add document %s: %s", doc_id, e)

    def get_collection_stats(self) -> Dict[str, int]:
        """Get document counts for all collections."""
        try:
            self._init_chroma()
            stats = {}
            for name in [COLLECTION_NAME, DART_COLLECTION, LITIGATION_COLLECTION]:
                try:
                    col = self._get_collection(name)
                    stats[name] = col.count()
                except Exception:
                    stats[name] = 0
            return stats
        except Exception:
            return {}

    # ----------------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------------

    @staticmethod
    def _build_agreement_text(row: Dict) -> str:
        """Build searchable text from an agreement row."""
        parts = []
        if row.get("company"):
            parts.append(f"Company: {row['company']}")
        if row.get("licensor_name"):
            parts.append(f"Licensor: {row['licensor_name']}")
        if row.get("licensee_name"):
            parts.append(f"Licensee: {row['licensee_name']}")
        if row.get("tech_name"):
            parts.append(f"Technology: {row['tech_name']}")
        if row.get("tech_category"):
            parts.append(f"Category: {row['tech_category']}")
        if row.get("royalty_rate"):
            unit = row.get("royalty_unit", "%")
            parts.append(f"Royalty: {row['royalty_rate']}{unit}")
        if row.get("upfront_amount"):
            parts.append(f"Upfront: ${row['upfront_amount']:,.0f}")
        if row.get("territory"):
            parts.append(f"Territory: {row['territory']}")
        if row.get("reasoning"):
            parts.append(f"Details: {row['reasoning'][:300]}")
        return " | ".join(parts) if parts else "No data"
