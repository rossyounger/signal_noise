"""
Reference content fetcher for external hypothesis documents.
Supports PDF extraction and web page extraction with caching.
"""

from __future__ import annotations

import logging
from typing import Optional
from datetime import datetime, timedelta

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


async def fetch_reference_content(
    url: str,
    timeout: int = 30
) -> Optional[str]:
    """
    Download and extract text content from a URL.
    
    Supports:
    - PDF files (via pypdf or pdfplumber)
    - Web pages (via BeautifulSoup)
    
    Args:
        url: URL to fetch content from
        timeout: Request timeout in seconds
        
    Returns:
        Extracted text content, or None if fetch/extraction fails
    """
    
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            logger.info(f"Fetching reference content from: {url}")
            response = await client.get(url)
            response.raise_for_status()
            
            content_type = response.headers.get('content-type', '').lower()
            
            # Handle PDF content
            if 'application/pdf' in content_type or url.lower().endswith('.pdf'):
                return await _extract_pdf_text(response.content, url)
            
            # Handle HTML/text content
            elif 'text/html' in content_type or 'text/plain' in content_type:
                return _extract_html_text(response.text, url)
            
            else:
                logger.warning(f"Unsupported content type: {content_type} for URL: {url}")
                return None
                
    except httpx.HTTPError as e:
        logger.error(f"HTTP error fetching {url}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error fetching reference content from {url}: {e}")
        return None


async def _extract_pdf_text(pdf_content: bytes, url: str) -> Optional[str]:
    """
    Extract text from PDF content.
    
    Args:
        pdf_content: Raw PDF bytes
        url: URL for logging purposes
        
    Returns:
        Extracted text or None on failure
    """
    try:
        # Try pypdf first (lighter dependency)
        try:
            from pypdf import PdfReader
            from io import BytesIO
            
            reader = PdfReader(BytesIO(pdf_content))
            text_parts = []
            
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
            
            full_text = "\n\n".join(text_parts)
            logger.info(f"Extracted {len(full_text)} characters from PDF via pypdf")
            return full_text
            
        except ImportError:
            # Fall back to pdfplumber if available
            try:
                import pdfplumber
                from io import BytesIO
                
                text_parts = []
                with pdfplumber.open(BytesIO(pdf_content)) as pdf:
                    for page in pdf.pages:
                        text = page.extract_text()
                        if text:
                            text_parts.append(text)
                
                full_text = "\n\n".join(text_parts)
                logger.info(f"Extracted {len(full_text)} characters from PDF via pdfplumber")
                return full_text
                
            except ImportError:
                logger.error("No PDF extraction library available (pypdf or pdfplumber)")
                return None
                
    except Exception as e:
        logger.error(f"Error extracting PDF text from {url}: {e}")
        return None


def _extract_html_text(html_content: str, url: str) -> Optional[str]:
    """
    Extract readable text from HTML content.
    
    Args:
        html_content: HTML string
        url: URL for logging purposes
        
    Returns:
        Extracted text or None on failure
    """
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
        
        # Get text content
        text = soup.get_text(separator='\n', strip=True)
        
        # Clean up whitespace
        lines = [line.strip() for line in text.split('\n')]
        lines = [line for line in lines if line]  # Remove empty lines
        text = '\n'.join(lines)
        
        logger.info(f"Extracted {len(text)} characters from HTML")
        return text
        
    except Exception as e:
        logger.error(f"Error extracting HTML text from {url}: {e}")
        return None


async def get_cached_reference(
    hypothesis_id: str,
    db_connection,
    max_age_days: int = 30
) -> Optional[str]:
    """
    Retrieve cached reference content if available and not expired.
    
    Args:
        hypothesis_id: UUID of hypothesis
        db_connection: Database connection
        max_age_days: Maximum age of cache in days
        
    Returns:
        Cached text content or None if not cached/expired
    """
    try:
        cutoff_date = datetime.now() - timedelta(days=max_age_days)
        
        result = await db_connection.fetchrow(
            """
            SELECT full_text, fetched_at
            FROM hypothesis_reference_cache
            WHERE hypothesis_id = $1 AND fetched_at > $2
            """,
            hypothesis_id,
            cutoff_date
        )
        
        if result:
            logger.info(f"Cache hit for hypothesis {hypothesis_id}")
            return result['full_text']
        
        logger.info(f"Cache miss for hypothesis {hypothesis_id}")
        return None
        
    except Exception as e:
        logger.error(f"Error retrieving cached reference: {e}")
        return None


async def cache_reference_content(
    hypothesis_id: str,
    full_text: str,
    db_connection
) -> bool:
    """
    Cache fetched reference content in database.
    
    Args:
        hypothesis_id: UUID of hypothesis
        full_text: Text content to cache
        db_connection: Database connection
        
    Returns:
        True if caching successful, False otherwise
    """
    try:
        await db_connection.execute(
            """
            INSERT INTO hypothesis_reference_cache 
            (hypothesis_id, full_text, character_count, fetched_at, updated_at)
            VALUES ($1, $2, $3, NOW(), NOW())
            ON CONFLICT (hypothesis_id) 
            DO UPDATE SET 
                full_text = EXCLUDED.full_text,
                character_count = EXCLUDED.character_count,
                fetched_at = NOW(),
                updated_at = NOW()
            """,
            hypothesis_id,
            full_text,
            len(full_text)
        )
        
        logger.info(f"Cached {len(full_text)} characters for hypothesis {hypothesis_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error caching reference content: {e}")
        return False
