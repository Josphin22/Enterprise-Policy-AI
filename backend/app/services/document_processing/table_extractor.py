"""
TableExtractor detects and extracts structured tabular data from PDF, DOCX, and plain text.
Formats extracted tables into clean, searchable markdown pipe-delimited tables.
Example:
| Policy | Days | Approval |
| --- | --- | --- |
| Annual Leave | 18 | Manager |
"""
import re
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("enterprise_rag.document_processing.table")


class TableExtractor:
    """
    Robust table extractor supporting:
    1. PyMuPDF page-level vector/grid table extraction (find_tables).
    2. Python-docx table extraction (doc.tables).
    3. Text-based heuristic table detection (pipes, tabs, aligned columns).
    """

    @staticmethod
    def format_markdown_table(rows: List[List[str]]) -> str:
        """
        Convert a 2D list of cell strings into a standard markdown pipe-delimited table.
        Clean cells of inner newlines and redundant spaces.
        """
        if not rows:
            return ""

        # Normalize rows
        clean_rows: List[List[str]] = []
        max_cols = 0
        for r in rows:
            cleaned_row = [re.sub(r"\s+", " ", str(cell or "")).strip() for cell in r]
            if any(c for c in cleaned_row):  # Row not entirely empty
                clean_rows.append(cleaned_row)
                if len(cleaned_row) > max_cols:
                    max_cols = len(cleaned_row)

        if not clean_rows or max_cols == 0:
            return ""

        # Pad rows to uniform column count
        padded_rows = []
        for r in clean_rows:
            if len(r) < max_cols:
                padded_rows.append(r + [""] * (max_cols - len(r)))
            else:
                padded_rows.append(r)

        # Header row + separator line + data rows
        header = padded_rows[0]
        separator = ["---"] * max_cols

        lines = [
            "| " + " | ".join(header) + " |",
            "| " + " | ".join(separator) + " |",
        ]

        for data_row in padded_rows[1:]:
            lines.append("| " + " | ".join(data_row) + " |")

        return "\n".join(lines)

    def extract_tables_from_pdf_page(self, page: Any, page_num: int = 1) -> List[Dict[str, Any]]:
        """
        Extract tables from a PyMuPDF Page object using built-in layout analysis.
        """
        tables = []
        try:
            if hasattr(page, "find_tables"):
                found_tabs = page.find_tables()
                if found_tabs and hasattr(found_tabs, "tables"):
                    for idx, tab in enumerate(found_tabs.tables, start=1):
                        extracted_rows = tab.extract()
                        if extracted_rows and len(extracted_rows) >= 1:
                            md_table = self.format_markdown_table(extracted_rows)
                            if md_table:
                                tables.append({
                                    "table_index": idx,
                                    "page_number": page_num,
                                    "row_count": len(extracted_rows),
                                    "col_count": len(extracted_rows[0]) if extracted_rows else 0,
                                    "markdown": md_table,
                                    "bbox": getattr(tab, "bbox", None),
                                })
        except Exception as exc:
            logger.debug(f"PDF table detection note on page {page_num}: {exc}")

        return tables

    def extract_tables_from_docx_doc(self, doc: Any) -> List[Dict[str, Any]]:
        """
        Extract structured tables from a python-docx Document object.
        """
        tables = []
        try:
            if hasattr(doc, "tables"):
                for idx, table in enumerate(doc.tables, start=1):
                    raw_rows = []
                    for row in table.rows:
                        row_cells = [cell.text.strip() for cell in row.cells]
                        raw_rows.append(row_cells)

                    if raw_rows:
                        md_table = self.format_markdown_table(raw_rows)
                        if md_table:
                            tables.append({
                                "table_index": idx,
                                "page_number": None,
                                "row_count": len(raw_rows),
                                "col_count": len(raw_rows[0]) if raw_rows else 0,
                                "markdown": md_table,
                            })
        except Exception as exc:
            logger.warning(f"DOCX table extraction note: {exc}")

        return tables

    def detect_text_tables(self, text: str) -> List[Dict[str, Any]]:
        """
        Detect text-based tabular lines (e.g. pipe-delimited or tab-delimited records).
        """
        tables = []
        lines = text.split("\n")
        pipe_buffer: List[List[str]] = []

        def flush_buffer():
            if len(pipe_buffer) >= 2:
                md_table = self.format_markdown_table(pipe_buffer)
                if md_table:
                    tables.append({
                        "table_index": len(tables) + 1,
                        "row_count": len(pipe_buffer),
                        "col_count": len(pipe_buffer[0]),
                        "markdown": md_table,
                    })
            pipe_buffer.clear()

        for line in lines:
            stripped = line.strip()
            # If line has 2 or more pipes and looks like table row:
            if stripped.count("|") >= 2 and not stripped.startswith("http"):
                cells = [c.strip() for c in stripped.split("|") if c.strip() or len(stripped.split("|")) > 2]
                if len(cells) >= 2:
                    pipe_buffer.append(cells)
                    continue

            # If line has 2 or more tab delimiters
            if "\t" in stripped and len(stripped.split("\t")) >= 2:
                cells = [c.strip() for c in stripped.split("\t") if c.strip()]
                if len(cells) >= 2:
                    pipe_buffer.append(cells)
                    continue

            flush_buffer()

        flush_buffer()
        return tables


table_extractor = TableExtractor()
