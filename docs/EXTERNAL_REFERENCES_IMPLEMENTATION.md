# External Hypothesis References - Implementation Summary

## Overview
Implemented hybrid storage for hypotheses with external reference documents (papers, articles, books), enabling both fast browsing with summaries and deep LLM analysis with full context.

## Changes Made

### 1. Database Schema (`sql/005_add_hypothesis_references.sql`)
- Added `reference_url` and `reference_type` columns to `hypotheses` table
- Created `hypothesis_reference_cache` table for caching fetched reference content
- Supports paper, article, book, and website reference types

### 2. Backend - Reference Fetching (`src/analysis/reference_fetcher.py`)
**New module** with functions for:
- `fetch_reference_content(url)` - Downloads and extracts text from PDFs and web pages
- `get_cached_reference(hypothesis_id, db_connection)` - Retrieves cached content
- `cache_reference_content(hypothesis_id, full_text, db_connection)` - Stores fetched content
- PDF extraction via pypdf/pdfplumber
- HTML extraction via BeautifulSoup
- 30-day cache TTL for papers, 7 days for web pages

### 3. Backend - Enhanced Analysis (`src/analysis/hypothesis.py`)
Updated `check_hypothesis()` function with new parameters:
- `hypothesis_description` - Multi-paragraph summary
- `reference_url` - Link to full document
- `include_full_reference` - User toggle for deep analysis
- `hypothesis_id` & `db_connection` - Required for caching

**Analysis modes:**
- **Default (summary only)**: Fast, uses hypothesis_text + description
- **Deep (full reference)**: Fetches and includes complete document in LLM context

### 4. Backend - API Updates (`src/api.py`)
Updated models and endpoints:
- `HypothesisCreate` - Added reference_url and reference_type fields
- `HypothesisView` - Includes reference metadata in list view
- `CheckHypothesisRequest` - Added parameters for reference analysis
- **NEW** `GET /hypotheses/{id}/reference` - Fetches full reference document (with caching)
- Updated queries to include reference fields

### 5. Frontend - Hypothesis Table (`web/src/app/hypotheses/page.tsx`)
- External link icon next to hypotheses with references
- Reference type badge (paper/article/book/website)
- Clickable links open reference in new tab

### 6. Frontend - Create Form (`web/src/app/hypotheses/page.tsx`)
Added fields:
- **Reference URL** - Optional text input with URL validation
- **Reference Type** - Dropdown (Paper, Article, Book, Website)
- **Description** - Expanded to 4 rows for multi-paragraph summaries

### 7. Frontend - Analysis Workbench (`web/src/app/segments/[segmentId]/analyze/page.tsx`)
Enhanced evidence analysis section:
- **Reference indicator** - Shows "📄 Based on: [type] reference" with link
- **"Use full reference document" checkbox** - User-controlled deep analysis
  - Tooltip: "Include complete paper in analysis (uses more AI tokens, takes longer)"
  - Only visible for hypotheses with reference_url
- **Analysis mode badge** - Shows "Analyzed with: Summary only" or "Full reference"
- Reference type badges in hypothesis selection modal

### 8. Test Data - Big World Hypothesis (`scripts/add_bigworld_hypothesis.py`)
Created script to populate database with example:
- **Hypothesis**: "For many learning problems, the world is multiple orders of magnitude larger than the agent, requiring approximate solutions."
- **Description**: Multi-paragraph summary with key arguments and empirical support
- **Reference**: http://openreview.net/pdf?id=Sv7DazuCn8
- **Type**: paper

## Usage Workflow

### Creating a Hypothesis with Reference
1. Navigate to `/hypotheses`
2. Click "Create New Hypothesis"
3. Enter hypothesis text (brief statement)
4. Enter multi-paragraph description (3-5 paragraphs for complex papers)
5. Paste reference URL (e.g., PDF link)
6. Select reference type from dropdown
7. Click "Create"

### Analyzing Evidence Against Referenced Hypothesis
1. Navigate to segment analysis page
2. Select or link hypothesis with reference
3. Notice the "📄 Based on: [type] reference" indicator
4. **For quick screening**: Leave checkbox unchecked, click "Run Evidence Analysis"
   - Uses summary only (fast, lower token cost)
5. **For nuanced evidence**: Check "Use full reference document", then click "Run Evidence Analysis"
   - Fetches and includes full paper in LLM context (slower, higher token cost)
6. Analysis result shows badge indicating which mode was used
7. Edit analysis if needed, then save

## Technical Details

### Caching Strategy
- First analysis with full reference: Fetches from URL and caches in database
- Subsequent analyses: Uses cached content (no network request)
- Cache invalidation: Automatic after 30 days (papers) or 7 days (web pages)
- Character count stored for token estimation

### Token Management
- Summary-only analysis: Typically <1k tokens for hypothesis context
- Full reference analysis: Can be 20k+ tokens (Big World paper is ~6k words)
- User controls cost via explicit checkbox selection
- Cache eliminates repeated download overhead

### Error Handling
- PDF fetch fails → Falls back to summary-only analysis
- Invalid URL → Shows warning in UI
- Network errors → Gracefully degrades to cached or summary mode
- Missing pypdf/pdfplumber → Logs error, returns None

## Files Modified
- `sql/005_add_hypothesis_references.sql` (NEW)
- `src/analysis/reference_fetcher.py` (NEW)
- `src/analysis/hypothesis.py` (MODIFIED)
- `src/api.py` (MODIFIED)
- `web/src/app/hypotheses/page.tsx` (MODIFIED)
- `web/src/app/segments/[segmentId]/analyze/page.tsx` (MODIFIED)
- `scripts/add_bigworld_hypothesis.py` (NEW)
- `README.md` (MODIFIED)

## Dependencies Required
Add to `requirements.txt` or install manually:
```bash
pip install pypdf  # or pdfplumber as alternative
pip install beautifulsoup4
pip install httpx
```

## Migration Instructions
```bash
# 1. Run database migration
psql $SUPABASE_DB_URL < sql/005_add_hypothesis_references.sql

# 2. Install new Python dependencies
pip install pypdf beautifulsoup4 httpx

# 3. Optional: Add Big World Hypothesis example
export PYTHONPATH=.
python scripts/add_bigworld_hypothesis.py

# 4. Restart backend API
python -m uvicorn src.api:app --reload
```

## Benefits
✅ **Fast by default**: Most analyses use summaries (sufficient for clear verdicts)  
✅ **Deep when needed**: Full paper context available for complex/nuanced evidence  
✅ **Cost control**: Users explicitly choose when to spend tokens on full context  
✅ **Provenance**: Always links back to source material  
✅ **Performance**: Caching eliminates repeated downloads  
✅ **Flexibility**: Works for both simple hypotheses and complex academic papers  

## Example Use Case: Big World Hypothesis
When analyzing a podcast segment about scaling AI systems:
1. **Quick check** (summary only): "Does this segment mention agent-environment size gaps?"
   - Fast screening of many segments
2. **Deep analysis** (full paper): Segment discusses continual learning and tracking
   - Toggle on full reference to verify alignment with paper's specific arguments
   - LLM has access to all 3 key arguments and empirical evidence
   - Can provide nuanced verdict citing specific sections

This hybrid approach balances speed for exploration with depth for validation.
