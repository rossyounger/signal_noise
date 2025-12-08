'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';

interface DocumentContent {
  document_id: string;
  content_text: string | null;
  content_html: string | null;
}

interface DocumentSegment {
  id: string;
  text: string;
  segment_status: string;
  created_at: string;
}

interface SelectionData {
  text: string;
  html: string;
  startOffset: number | undefined;
  endOffset: number | undefined;
}

export default function SegmentationWorkbenchPage() {
  const params = useParams();
  const documentId = params.documentId as string;

  const [document, setDocument] = useState<DocumentContent | null>(null);
  const [segments, setSegments] = useState<DocumentSegment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selection, setSelection] = useState<SelectionData | null>(null);
  const [creating, setCreating] = useState(false);

  const contentRef = useRef<HTMLDivElement>(null);

  const clearHighlights = useCallback(() => {
    if (!contentRef.current) return;
    const existingHighlights = contentRef.current.querySelectorAll('.selection-highlight');
    existingHighlights.forEach((el) => {
      const parent = el.parentNode;
      if (parent) {
        while (el.firstChild) {
          parent.insertBefore(el.firstChild, el);
        }
        parent.removeChild(el);
        parent.normalize();
      }
    });
  }, []);

  const fetchDocument = useCallback(async () => {
    try {
      const res = await fetch(`http://127.0.0.1:8000/documents/${documentId}/content`);
      if (!res.ok) throw new Error('Failed to fetch document');
      const data = await res.json();
      setDocument(data);
    } catch (err: any) {
      setError(err.message);
    }
  }, [documentId]);

  const fetchSegments = useCallback(async () => {
    try {
      const res = await fetch(`http://127.0.0.1:8000/documents/${documentId}/segments`);
      if (!res.ok) throw new Error('Failed to fetch segments');
      const data = await res.json();
      setSegments(data);
    } catch (err: any) {
      console.error('Failed to fetch segments:', err);
    }
  }, [documentId]);

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      // Clear selection when document changes
      setSelection(null);
      window.getSelection()?.removeAllRanges();
      // Clear highlights - using stable ref, no need in deps
      if (contentRef.current) {
        const existingHighlights = contentRef.current.querySelectorAll('.selection-highlight');
        existingHighlights.forEach((el) => {
          const parent = el.parentNode;
          if (parent) {
            while (el.firstChild) {
              parent.insertBefore(el.firstChild, el);
            }
            parent.removeChild(el);
            parent.normalize();
          }
        });
      }
      await Promise.all([fetchDocument(), fetchSegments()]);
      setLoading(false);
    };
    loadData();
  }, [documentId, fetchDocument, fetchSegments]);

  const handleMouseUp = useCallback((e: MouseEvent) => {
    // Only handle if clicking within content area
    if (!contentRef.current || !contentRef.current.contains(e.target as Node)) {
      return;
    }

    // Small delay to ensure selection is complete
    setTimeout(() => {
      const sel = window.getSelection();
      if (!sel || sel.isCollapsed || !contentRef.current || !document?.content_text) {
        return;
      }

      const range = sel.getRangeAt(0);
      
      // Check if selection is within our content area
      if (!contentRef.current.contains(range.commonAncestorContainer)) {
        return;
      }

      const selectedText = sel.toString().trim();
      if (!selectedText || selectedText.length === 0) {
        return;
      }

      // Get the HTML of the selection
      const clonedContents = range.cloneContents();
      const tempDiv = window.document.createElement('div');
      tempDiv.appendChild(clonedContents);
      const html = tempDiv.innerHTML;

      // Clear browser selection immediately
      sel.removeAllRanges();

      // Wrap selection in highlight span BEFORE calculating offsets (so DOM is stable)
      let highlightSpan: HTMLSpanElement | null = null;
      try {
        // Clear any existing highlights first
        clearHighlights();

        // Wrap the selection
        highlightSpan = window.document.createElement('span');
        highlightSpan.className = 'selection-highlight';
        highlightSpan.style.backgroundColor = '#dbeafe';
        highlightSpan.style.color = '#1e40af';
        highlightSpan.style.padding = '2px 0';
        highlightSpan.style.borderRadius = '2px';
        
        try {
          range.surroundContents(highlightSpan);
        } catch (e) {
          // If surroundContents fails, extract and wrap
          const contents = range.extractContents();
          highlightSpan.appendChild(contents);
          range.insertNode(highlightSpan);
        }
      } catch (e) {
        console.warn('Failed to highlight selection:', e);
        return;
      }

      // Calculate offsets by finding selected text in content_text
      const cleanSelected = selectedText.trim();
      
      // Try to find the text in content_text
      let startOffset = document.content_text.indexOf(cleanSelected);
      
      // If exact match fails, try with first 100 chars as search hint
      if (startOffset === -1 && cleanSelected.length > 100) {
        const searchHint = cleanSelected.substring(0, 100);
        startOffset = document.content_text.indexOf(searchHint);
      }
      
      // If still not found, try normalized whitespace
      if (startOffset === -1) {
        const normalize = (s: string) => s.replace(/\s+/g, ' ').trim();
        const normalizedSelected = normalize(cleanSelected);
        const normalizedContent = normalize(document.content_text);
        const normalizedIndex = normalizedContent.indexOf(normalizedSelected);
        
        if (normalizedIndex !== -1) {
          // Approximate: use normalized index (close enough, backend will refine)
          startOffset = normalizedIndex;
        }
      }
      
      // Last resort: send None and let backend figure it out
      const endOffset = startOffset !== -1 ? startOffset + cleanSelected.length : undefined;

      setSelection({
        text: cleanSelected,
        html,
        startOffset: startOffset !== -1 ? startOffset : undefined,
        endOffset,
      });
    }, 10);
  }, [document, clearHighlights]);

  // Set up mouseup listener to capture selection
  useEffect(() => {
    if (!document || !contentRef.current) return;

    const contentEl = contentRef.current;

    // Small delay to ensure DOM is ready
    const timeoutId = setTimeout(() => {
      contentEl.addEventListener('mouseup', handleMouseUp);
    }, 100);

    return () => {
      clearTimeout(timeoutId);
      contentEl.removeEventListener('mouseup', handleMouseUp);
    };
  }, [handleMouseUp, document]);


  const handleCreateSegment = async () => {
    if (!selection) return;

    setCreating(true);
    try {
      const res = await fetch('http://127.0.0.1:8000/segments', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          document_id: documentId,
          text: selection.text,
          start_offset: selection.startOffset ?? null,
          end_offset: selection.endOffset ?? null,
          html: selection.html,
        }),
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to create segment');
      }

      // Clear selection, highlights, and refresh segments
      window.getSelection()?.removeAllRanges();
      clearHighlights();
      setSelection(null);
      await fetchSegments();
    } catch (err: any) {
      alert(`Error: ${err.message}`);
    } finally {
      setCreating(false);
    }
  };

  if (loading) {
    return (
      <main className="w-full px-4 py-6 lg:px-8">
        <div className="py-6">Loading document...</div>
      </main>
    );
  }

  if (error) {
    return (
      <main className="w-full px-4 py-6 lg:px-8">
        <div className="py-6 text-red-600">Error: {error}</div>
      </main>
    );
  }

  return (
    <main className="w-full px-4 py-6 lg:px-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-4">
          <Link
            href="/documents"
            className="text-indigo-600 hover:text-indigo-800 text-sm flex items-center gap-1"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Back
          </Link>
          <h1 className="text-xl font-bold text-gray-900">Segmentation Workbench</h1>
        </div>

        <button
          onClick={handleCreateSegment}
          disabled={!selection || creating}
          className={`px-4 py-2 rounded-md text-sm font-semibold shadow-sm transition-all ${
            selection && !creating
              ? 'bg-indigo-600 text-white hover:bg-indigo-700 active:bg-indigo-800'
              : 'bg-gray-200 text-gray-500 cursor-not-allowed'
          }`}
        >
          {creating ? (
            'Creating...'
          ) : selection ? (
            <span className="flex items-center gap-2">
              <span>Create Segment</span>
              {selection.startOffset !== undefined && selection.endOffset !== undefined ? (
                <span className="text-xs font-normal opacity-90">
                  [{selection.startOffset}→{selection.endOffset}] ({selection.text.length} chars)
                </span>
              ) : (
                <span className="text-xs font-normal opacity-90">
                  ({selection.text.length} chars)
                </span>
              )}
            </span>
          ) : (
            'Select text to create segment'
          )}
        </button>
      </div>

      {/* Segments Table - Compact */}
      {segments.length > 0 && (
        <div className="mb-3 bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
          <table className="w-full text-xs">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-3 py-1.5 text-left font-medium text-gray-500 uppercase tracking-wider w-16">
                  #
                </th>
                <th className="px-3 py-1.5 text-left font-medium text-gray-500 uppercase tracking-wider">
                  Segment Preview
                </th>
                <th className="px-3 py-1.5 text-left font-medium text-gray-500 uppercase tracking-wider w-24">
                  Status
                </th>
                <th className="px-3 py-1.5 text-left font-medium text-gray-500 uppercase tracking-wider w-28">
                  Created
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {segments.map((seg, idx) => (
                <tr key={seg.id} className="hover:bg-gray-50">
                  <td className="px-3 py-1.5 text-gray-400">{segments.length - idx}</td>
                  <td className="px-3 py-1.5 text-gray-700 truncate max-w-0">
                    <span className="truncate block">{seg.text.slice(0, 150)}</span>
                  </td>
                  <td className="px-3 py-1.5">
                    <span className="inline-flex px-2 py-0.5 text-xs font-medium rounded-full bg-gray-100 text-gray-600">
                      {seg.segment_status}
                    </span>
                  </td>
                  <td className="px-3 py-1.5 text-gray-500">
                    {new Date(seg.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {segments.length === 0 && (
        <div className="mb-3 bg-gray-50 rounded-lg border border-dashed border-gray-300 px-4 py-2 text-sm text-gray-500 text-center">
          No segments yet. Select text below and click "Create Segment" to get started.
        </div>
      )}

      {/* HTML Content Viewer */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
        <div className="px-4 py-2 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
          <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">Document Content</span>
          {selection && (
            <span className="text-xs text-indigo-600 font-medium">
              Selected: {selection.text.slice(0, 50)}{selection.text.length > 50 ? '...' : ''}
            </span>
          )}
        </div>
        <div
          ref={contentRef}
          className="p-6 prose prose-sm max-w-none text-gray-900 selection:bg-indigo-100 selection:text-indigo-900 max-h-[70vh] overflow-y-auto"
          dangerouslySetInnerHTML={{
            __html: document?.content_html || document?.content_text || '<p class="text-gray-400">No content available</p>',
          }}
        />
      </div>
    </main>
  );
}
