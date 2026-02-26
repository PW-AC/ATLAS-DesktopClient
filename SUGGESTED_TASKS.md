# Suggested Tasks for ACENCIA ATLAS

This document lists identified tasks for improving the performance, UI/UX, and codebase structure of the ACENCIA ATLAS application, specifically focusing on the Document Archive and Processing components.

## Performance

1.  **Lazy Loading for PDF Thumbnails**
    - **Current:** `_ThumbnailWorker` in `archive_view.py` and `PDFViewerDialog` renders all pages of a PDF upfront. For large PDFs, this causes UI freeze or high memory usage.
    - **Task:** Implement lazy loading in `QListWidget` or `QListView`. Only render thumbnails for pages currently visible in the viewport.
    - **Impact:** Significant performance improvement for large documents.

2.  **Server-Side Pagination**
    - **Current:** `DocumentLoadWorker` fetches all documents at once (`list_documents`). As the archive grows (10k+ docs), this will become slow.
    - **Task:** Update `DocumentsAPI.list_documents` and `ArchiveView` to support pagination (e.g., `page=1&limit=50`). Add "Load More" or proper pagination controls in the UI.
    - **Impact:** Scalability for large datasets.

3.  **Optimize PDF Processing (Deduplication)**
    - **Current:** `DocumentProcessor` uses `_process_pdf_content_optimized` to open PDFs once. However, ensuring this is used consistently across all code paths (especially fallback logic) is crucial.
    - **Task:** Audit all `fitz.open()` calls. Ensure the `fitz.Document` object is passed around rather than re-opening the file.
    - **Impact:** Reduced I/O and faster processing.

4.  **Database Indexing**
    - **Current:** Filtering by `box_type`, `created_at`, `is_gdv` is frequent.
    - **Task:** Verify that the backend database has indices on these columns.
    - **Impact:** Faster filtering and sorting in the Archive View.

## UI/UX

1.  **[COMPLETED] Archive View Visual Rework**
    - **Current:** Standard `QTableWidget` with colored text. Functional but dated.
    - **Task:**
        - Replace text-based "Source" and "KI" columns with **Badge/Pill** styling (using `QStyledItemDelegate`).
        - Increase row height for better touch/readability.
        - Add file type icons (PDF, Excel, GDV) next to filenames.
    - **Status:** Completed. Implemented `QFileIconProvider` for native file icons and fixed `BadgeDelegate` rendering. Row height increased to 44px.
    - **Impact:** Modern, professional look and better readability.

2.  **Card View Toggle**
    - **Current:** Only Table View available.
    - **Task:** Add a toggle button to switch between Table View and a "Grid/Card View". Cards should show a thumbnail preview (if PDF) and key metadata.
    - **Impact:** Better visual browsing for documents.

3.  **Dashboard View**
    - **Current:** No overview of system status.
    - **Task:** Create a Dashboard tab showing:
        - Documents processed today/week.
        - Cost overview (OpenRouter usage).
        - Error rates (failed classifications).
    - **Impact:** Better transparency for the user.

4.  **Improved Search**
    - **Current:** Simple text filter.
    - **Task:** Implement "Search as you type" with a debounce mechanism. Highlight matching text in the table.
    - **Impact:** Faster information retrieval.

## Refactoring

1.  **[PRIORITY] Extract Dialogs**
    - **Current:** `PDFViewerDialog` and `DuplicateCompareDialog` are large classes inside `archive_view.py`.
    - **Task:** Move these classes to `src/ui/dialogs/pdf_viewer.py` and `src/ui/dialogs/duplicate_compare.py`.
    - **Impact:** Better code organization and maintainability.

2.  **Worker Extraction**
    - **Current:** `DocumentLoadWorker`, `UploadWorker`, `AIRenameWorker` are in `archive_view.py`.
    - **Task:** Move all worker classes to `src/ui/archive/workers.py`.
    - **Impact:** Cleaner `ArchiveView` class, easier to test workers in isolation.
