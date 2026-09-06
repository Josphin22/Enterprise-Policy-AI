import logging
from pathlib import Path
from typing import List, Optional
import docx
from app.services.document_processing.base_loader import BaseDocumentLoader, ExtractedBlock

logger = logging.getLogger("enterprise_rag.document_processing.docx")


class DocxLoader(BaseDocumentLoader):
    """
    Extracts structured text from DOCX policy manuals using python-docx.
    Captures paragraphs, headings, and table rows with section tracking.
    """

    def load(self, file_path: Path, **kwargs) -> List[ExtractedBlock]:
        if not file_path.exists():
            raise FileNotFoundError(f"DOCX document not found at: {file_path}")

        extracted_blocks: List[ExtractedBlock] = []

        try:
            doc = docx.Document(str(file_path))
            current_section: Optional[str] = None
            accumulated_paragraphs: List[str] = []

            for paragraph in doc.paragraphs:
                text = paragraph.text.strip()
                if not text:
                    continue

                style_name = paragraph.style.name.lower() if paragraph.style else ""
                is_heading = "heading" in style_name or "title" in style_name

                if is_heading:
                    # Flush previously accumulated paragraphs as a section block
                    if accumulated_paragraphs:
                        block_text = "\n\n".join(accumulated_paragraphs)
                        extracted_blocks.append(
                            ExtractedBlock(
                                text=block_text,
                                page_number=None,
                                section=current_section,
                                metadata={
                                    "filename": file_path.name,
                                    "file_type": "docx",
                                    "section": current_section,
                                },
                            )
                        )
                        accumulated_paragraphs = []

                    current_section = text
                    accumulated_paragraphs.append(f"## {text}")
                else:
                    accumulated_paragraphs.append(text)

            # Flush any remaining paragraphs
            if accumulated_paragraphs:
                block_text = "\n\n".join(accumulated_paragraphs)
                extracted_blocks.append(
                    ExtractedBlock(
                        text=block_text,
                        page_number=None,
                        section=current_section,
                        metadata={
                            "filename": file_path.name,
                            "file_type": "docx",
                            "section": current_section,
                        },
                    )
                )

            # Extract tables
            for table_idx, table in enumerate(doc.tables):
                table_rows: List[str] = []
                for row in table.rows:
                    row_cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    if row_cells:
                        table_rows.append(" | ".join(row_cells))

                if table_rows:
                    table_text = f"[Table {table_idx + 1}]\n" + "\n".join(table_rows)
                    extracted_blocks.append(
                        ExtractedBlock(
                            text=table_text,
                            page_number=None,
                            section=f"{current_section or 'General'} - Table {table_idx + 1}",
                            metadata={
                                "filename": file_path.name,
                                "file_type": "docx",
                                "is_table": True,
                            },
                        )
                    )

            logger.info(f"DocxLoader extracted {len(extracted_blocks)} structural blocks from {file_path.name}")

        except Exception as exc:
            logger.error(f"Failed to parse DOCX file '{file_path}': {exc}", exc_info=True)
            raise ValueError(f"Corrupted or unreadable DOCX document: {exc}") from exc

        return extracted_blocks


docx_loader = DocxLoader()
