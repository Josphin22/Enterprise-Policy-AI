# 22. Limitations of the Current Implementation

1. **OCR Support:** Currently processes digital text PDFs, DOCX, and TXT files; physical scanned documents containing bitmap images require external Optical Character Recognition (OCR) pre-processing.
2. **Complex Graphical Tables:** While structured text tables in Word and PDFs are parsed, nested graphical charts and diagrams are not visually interpreted.
3. **Local Hardware Dependency:** Generative inference speed depends on host CPU/GPU capabilities. High concurrent user volume requires multi-worker GPU acceleration.
4. **Context Window Boundary:** Multi-turn conversational memory is bounded to recent message turns to avoid saturating the local LLM context window.
5. **Residual Model Non-Determinism:** While low-temperature sampling ($T=0.1$) minimizes variability, generative language models retain intrinsic probabilistic variation.
