"""
Enterprise Policy AI - Hybrid Search & Retrieval Engine (Phase 9)
Coordinates Semantic Vector Search (FAISS + SentenceTransformers) and
Keyword Search (PostgreSQL/SQLite), performs Reciprocal Rank Fusion (RRF)
and score normalization, removes duplicates, preserves exact numbers/dates,
enforces metadata filtering, and balances source diversity.
"""

import re
import time
import logging
from typing import List, Dict, Any, Optional, Set, Union, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.config import settings
from app.models.document import Document
from app.models.document_metadata import DocumentMetadata
from app.rag.schemas import CandidateChunk, MetadataFilter
from app.rag.retriever import rag_retriever, RAGRetriever
from app.rag.keyword_search import keyword_search_engine, KeywordSearchEngine
from app.rag.reranker import reranker_service, RerankerService

logger = logging.getLogger("enterprise_rag.rag.hybrid_retriever")


class HybridRetriever:
    """
    Orchestrates Semantic (FAISS) and Keyword (DB) search pipelines,
    merges candidates using Reciprocal Rank Fusion and weighted scoring,
    eliminates duplicate text chunks, enforces metadata filtering,
    and boosts exact numbers and dates.
    """

    def __init__(
        self,
        semantic_retriever: Optional[RAGRetriever] = None,
        keyword_engine: Optional[KeywordSearchEngine] = None,
        reranker: Optional[RerankerService] = None,
    ):
        self.semantic_retriever = semantic_retriever or rag_retriever
        self.keyword_engine = keyword_engine or keyword_search_engine
        self.reranker = reranker or reranker_service

    def _filter_semantic_candidates_by_metadata(
        self,
        candidates: List[CandidateChunk],
        filters: MetadataFilter,
        db: Optional[Session],
    ) -> List[CandidateChunk]:
        """
        Filter FAISS semantic candidates against document metadata
        (file_type, owner_id, status, department) using database verification.
        """
        if not candidates or not db:
            return candidates

        doc_ids = list({c.document_id for c in candidates if c.document_id})
        if not doc_ids:
            return candidates

        stmt = (
            select(
                Document.id,
                Document.file_type,
                Document.owner_id,
                Document.processing_status,
                DocumentMetadata.department,
            )
            .outerjoin(DocumentMetadata, Document.id == DocumentMetadata.document_id)
            .where(Document.id.in_(doc_ids))
        )
        rows = db.execute(stmt).all()
        doc_meta_map = {
            r[0]: {
                "file_type": (r[1] or "").lower(),
                "owner_id": r[2],
                "status": (r[3] or "").lower(),
                "department": (r[4] or "").lower() if r[4] else None,
            }
            for r in rows
        }

        f_file_type = filters.file_type.lower().strip() if filters.file_type else None
        allowed_ft = set()
        if f_file_type:
            allowed_ft = {
                f_file_type if f_file_type.startswith(".") else f".{f_file_type}",
                f_file_type.lstrip("."),
            }

        f_owner_id = str(filters.owner_id) if filters.owner_id else None
        f_status = filters.status.lower().strip() if filters.status else None
        f_dept = filters.department.lower().strip() if filters.department else None
        f_allowed_doc_ids = set(str(d) for d in filters.allowed_document_ids) if filters.allowed_document_ids is not None else None

        filtered: List[CandidateChunk] = []
        for c in candidates:
            # Enforce allowed_document_ids check strictly
            if f_allowed_doc_ids is not None and str(c.document_id) not in f_allowed_doc_ids:
                continue

            d_info = doc_meta_map.get(c.document_id)
            if not d_info:
                # If metadata filter requires document attributes but doc not found in DB, skip
                if any([f_file_type, f_owner_id, f_status, f_dept]):
                    continue
                filtered.append(c)
                continue

            if f_file_type and d_info["file_type"] not in allowed_ft:
                continue
            if f_owner_id and str(d_info["owner_id"] or "") != f_owner_id:
                continue
            if f_status and d_info["status"] != f_status:
                continue
            if f_dept and (d_info["department"] or "") != f_dept:
                continue

            filtered.append(c)

        return filtered

    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        db: Optional[Session] = None,
        document_id: Optional[str] = None,
        filters: Optional[Union[MetadataFilter, Dict[str, Any]]] = None,
        min_score: Optional[float] = None,
        return_diagnostics: bool = False,
    ) -> Union[List[CandidateChunk], Tuple[List[CandidateChunk], Dict[str, Any]]]:
        """
        Execute full Phase 9 Hybrid Retrieval:
        1. Parse and extract entities (numbers, dates, currencies, keywords)
        2. Semantic vector search via FAISS
        3. Full-text keyword search via PostgreSQL / SQLite
        4. Apply metadata filtering across both streams
        5. Reciprocal Rank Fusion & normalized score combination
        6. Remove duplicate chunks by ID and text fingerprint
        7. Apply exact numerical & temporal preservation boost
        8. Source diversity balancing
        9. Optional neural reranking (if enabled)
        10. Compile diagnostic search telemetry
        """
        t_start = time.perf_counter()
        req_k = top_k or settings.RETRIEVAL_TOP_K
        k = max(1, min(req_k, 15))
        effective_min_score = min_score if min_score is not None else 0.10

        # Normalize filters
        active_filters = MetadataFilter()
        if filters:
            if isinstance(filters, MetadataFilter):
                active_filters = filters
            elif isinstance(filters, dict):
                active_filters = MetadataFilter(**filters)

        # Merge explicit document_id into filters if supplied
        if document_id:
            active_filters.document_id = str(document_id)

        # 1. Entity Extraction
        entities = self.keyword_engine.extract_search_entities(query)

        # 2. Semantic Search (FAISS)
        t_sem_start = time.perf_counter()
        semantic_candidates: List[CandidateChunk] = []
        try:
            semantic_candidates = self.semantic_retriever.retrieve(
                query=query,
                top_k=max(k * 2, 10),
                db=db,
                document_id=active_filters.document_id,
            )
            for c in semantic_candidates:
                c.source_type = "semantic"
                c.semantic_score = c.score
        except Exception as sem_exc:
            logger.warning(f"Semantic search encountered notice: {sem_exc}")
            semantic_candidates = []
        semantic_time_ms = round((time.perf_counter() - t_sem_start) * 1000, 2)

        # Apply secondary metadata filters to semantic candidates if any
        has_meta_filter = any([
            active_filters.file_type,
            active_filters.owner_id,
            active_filters.status,
            active_filters.department,
            active_filters.allowed_document_ids is not None,
        ])
        if has_meta_filter and db and semantic_candidates:
            semantic_candidates = self._filter_semantic_candidates_by_metadata(
                semantic_candidates, active_filters, db
            )

        # 3. Keyword Search (DB)
        t_kw_start = time.perf_counter()
        keyword_candidates: List[CandidateChunk] = []
        if db:
            try:
                keyword_candidates = self.keyword_engine.search(
                    query=query,
                    db=db,
                    top_k=max(k * 2, 10),
                    filters=active_filters,
                    min_score=0.05,
                )
            except Exception as kw_exc:
                logger.warning(f"Keyword search encountered notice: {kw_exc}")
                keyword_candidates = []
        keyword_time_ms = round((time.perf_counter() - t_kw_start) * 1000, 2)

        # 4. Result Merging, Deduplication & Reciprocal Rank Fusion (RRF)
        t_merge_start = time.perf_counter()
        merged_candidates = self._merge_and_fuse_candidates(
            query=query,
            semantic_candidates=semantic_candidates,
            keyword_candidates=keyword_candidates,
            entities=entities,
            top_k=max(k * 2, 12),
        )
        merge_time_ms = round((time.perf_counter() - t_merge_start) * 1000, 2)

        # 5. Source Diversity Balancing
        diverse_candidates = self._apply_source_diversity(merged_candidates, max_k=max(k, 5))

        # 6. Optional Reranker
        t_rerank_start = time.perf_counter()
        final_candidates = diverse_candidates
        if self.reranker.is_enabled:
            final_candidates = self.reranker.rerank(
                query=query,
                candidates=diverse_candidates,
                top_k=k,
            )
        else:
            final_candidates = diverse_candidates[:k]
        rerank_time_ms = round((time.perf_counter() - t_rerank_start) * 1000, 2)

        total_time_ms = round((time.perf_counter() - t_start) * 1000, 2)

        diagnostics = {
            "query": query,
            "detected_numbers": entities["numbers"],
            "detected_dates": entities["dates"],
            "detected_currencies": entities["currencies"],
            "detected_keywords": entities["keywords"],
            "semantic_count": len(semantic_candidates),
            "keyword_count": len(keyword_candidates),
            "merged_count": len(merged_candidates),
            "final_count": len(final_candidates),
            "latencies_ms": {
                "semantic_time_ms": semantic_time_ms,
                "keyword_time_ms": keyword_time_ms,
                "merge_time_ms": merge_time_ms,
                "rerank_time_ms": rerank_time_ms,
                "total_time_ms": total_time_ms,
            },
            "semantic_candidates": [
                {"id": c.chunk_id, "doc": c.filename, "score": c.score}
                for c in semantic_candidates[:5]
            ],
            "keyword_candidates": [
                {"id": c.chunk_id, "doc": c.filename, "score": c.score, "reasons": c.match_reasons}
                for c in keyword_candidates[:5]
            ],
            "final_candidates": [
                {"id": c.chunk_id, "doc": c.filename, "score": c.score, "source": c.source_type}
                for c in final_candidates
            ],
        }

        logger.info(
            f"Hybrid retrieval finished in {total_time_ms}ms: "
            f"{len(semantic_candidates)} sem, {len(keyword_candidates)} kw -> "
            f"{len(final_candidates)} final."
        )

        if return_diagnostics:
            return final_candidates, diagnostics

        return final_candidates

    def _merge_and_fuse_candidates(
        self,
        query: str,
        semantic_candidates: List[CandidateChunk],
        keyword_candidates: List[CandidateChunk],
        entities: Dict[str, List[str]],
        top_k: int = 10,
    ) -> List[CandidateChunk]:
        """
        Merge candidate lists using Reciprocal Rank Fusion (RRF) and normalized scoring.
        Deduplicates chunks by ID and text hash fingerprint.
        Applies exact number and date preservation boosts.
        """
        # Build maps for ranks
        sem_rank_map: Dict[str, int] = {}
        for rank, c in enumerate(semantic_candidates, start=1):
            sem_rank_map[c.chunk_id] = rank

        kw_rank_map: Dict[str, int] = {}
        for rank, c in enumerate(keyword_candidates, start=1):
            kw_rank_map[c.chunk_id] = rank

        # Deduplication registry: key -> CandidateChunk
        merged_by_id: Dict[str, CandidateChunk] = {}
        text_fingerprints: Dict[str, str] = {}  # norm_text -> chunk_id

        # Process Semantic candidates
        for c in semantic_candidates:
            norm_text = " ".join(c.text.strip().lower().split())
            if norm_text in text_fingerprints:
                continue
            text_fingerprints[norm_text] = c.chunk_id
            c_copy = c.model_copy()
            c_copy.source_type = "semantic"
            c_copy.semantic_score = c.score
            merged_by_id[c.chunk_id] = c_copy

        # Process Keyword candidates (merge or insert)
        for c in keyword_candidates:
            norm_text = " ".join(c.text.strip().lower().split())
            existing_id = text_fingerprints.get(norm_text) or (c.chunk_id if c.chunk_id in merged_by_id else None)

            if existing_id and existing_id in merged_by_id:
                # Merge into existing candidate
                existing = merged_by_id[existing_id]
                existing.source_type = "hybrid"
                existing.keyword_score = c.score
                for r in c.match_reasons:
                    if r not in existing.match_reasons:
                        existing.match_reasons.append(r)
            else:
                text_fingerprints[norm_text] = c.chunk_id
                c_copy = c.model_copy()
                c_copy.source_type = "keyword"
                c_copy.keyword_score = c.score
                merged_by_id[c.chunk_id] = c_copy

        # Compute fused score for every unique candidate
        numbers = entities.get("numbers", [])
        dates = entities.get("dates", [])
        currencies = entities.get("currencies", [])

        scored_candidates: List[CandidateChunk] = []
        for chunk_id, candidate in merged_by_id.items():
            s_rank = sem_rank_map.get(chunk_id, 100)
            k_rank = kw_rank_map.get(chunk_id, 100)

            # RRF component (k_constant = 60)
            rrf_sem = 0.60 / (60.0 + s_rank) if chunk_id in sem_rank_map else 0.0
            rrf_kw = 0.40 / (60.0 + k_rank) if chunk_id in kw_rank_map else 0.0
            rrf_score = rrf_sem + rrf_kw

            # Base weighted score
            s_score = candidate.semantic_score or 0.0
            k_score = candidate.keyword_score or 0.0

            if candidate.source_type == "hybrid":
                combined_score = 0.55 * s_score + 0.45 * k_score + 0.10
            elif candidate.source_type == "keyword":
                combined_score = k_score
            else:
                combined_score = s_score

            # Exact Number & Date preservation boosts
            lower_text = candidate.text.lower()
            exact_number_boost = 0.0
            for num in numbers:
                if num.lower() in lower_text:
                    exact_number_boost = max(exact_number_boost, 0.15)
                    if f"exact_num:{num}" not in candidate.match_reasons:
                        candidate.match_reasons.append(f"exact_num:{num}")

            exact_date_boost = 0.0
            for dt in dates:
                if dt.lower() in lower_text:
                    exact_date_boost = max(exact_date_boost, 0.15)
                    if f"exact_date:{dt}" not in candidate.match_reasons:
                        candidate.match_reasons.append(f"exact_date:{dt}")

            exact_currency_boost = 0.0
            for cur in currencies:
                if cur.lower() in lower_text or cur.replace(",", "").lower() in lower_text:
                    exact_currency_boost = max(exact_currency_boost, 0.20)
                    if f"exact_cur:{cur}" not in candidate.match_reasons:
                        candidate.match_reasons.append(f"exact_cur:{cur}")

            # Specific Document/Class/Policy identifier boost
            identifier_boost = 0.0
            candidate_fn = (candidate.filename or "").lower()
            lower_text = candidate.text.lower()
            q_lower = query.lower()

            # Class/level tokens: '10th', '11th', '12th', 'x standard', 'first year', etc.
            class_tokens = ["10th", "11th", "12th", "x standard", "xi standard", "first year", "second year"]
            for ct in class_tokens:
                if ct in q_lower:
                    if ct in candidate_fn or ct in lower_text:
                        identifier_boost += 0.40
                    else:
                        # Mismatched class (e.g. user asked 10th but candidate is 11th)
                        identifier_boost -= 0.35

            # Total normalized fused score [0.0, 1.0]
            final_score = max(
                0.0,
                min(
                    1.0,
                    round(
                        combined_score + exact_number_boost + exact_date_boost + exact_currency_boost + identifier_boost,
                        4,
                    ),
                ),
            )
            candidate.score = final_score
            scored_candidates.append(candidate)

        # Sort descending by fused score
        scored_candidates.sort(key=lambda x: x.score, reverse=True)
        return scored_candidates[:top_k]

    def _apply_source_diversity(
        self,
        candidates: List[CandidateChunk],
        max_k: int = 5,
    ) -> List[CandidateChunk]:
        """
        Prevent single-document dominance across multi-concept queries.
        Allocates chunks fairly across distinct documents if multiple documents match.
        """
        if len(candidates) <= max_k:
            return candidates

        doc_ids = [c.document_id for c in candidates if c.document_id]
        distinct_docs = list(dict.fromkeys(doc_ids))

        if len(distinct_docs) <= 1:
            return candidates[:max_k]

        selected: List[CandidateChunk] = []
        seen_ids: Set[str] = set()

        # Step 1: Pick the top chunk from each distinct document
        for d_id in distinct_docs:
            top_for_doc = next((c for c in candidates if c.document_id == d_id), None)
            if top_for_doc and top_for_doc.chunk_id not in seen_ids:
                selected.append(top_for_doc)
                seen_ids.add(top_for_doc.chunk_id)
            if len(selected) >= max_k:
                break

        # Step 2: Fill remaining slots by highest relevance score
        for c in candidates:
            if len(selected) >= max_k:
                break
            if c.chunk_id not in seen_ids:
                selected.append(c)
                seen_ids.add(c.chunk_id)

        # Preserve score descending order
        selected.sort(key=lambda x: x.score, reverse=True)
        return selected


# Global singleton instance
hybrid_retriever = HybridRetriever()
