'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';

interface HypothesisView {
  hypothesis_id: string;
  hypothesis_text: string | null;
  description: string | null;
  reference_url: string | null;
  reference_type: string | null;
  last_updated_at: string;
  evidence_count: number;
  latest_segment_id: string | null;
  latest_segment_text_preview: string | null;
  latest_document_id: string | null;
  latest_document_title: string | null;
}

export default function HypothesesPage() {
  const [hypotheses, setHypotheses] = useState<HypothesisView[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingHypothesisId, setEditingHypothesisId] = useState<string | null>(null);
  const [editHypothesisText, setEditHypothesisText] = useState('');
  const [editDescription, setEditDescription] = useState('');
  const [editError, setEditError] = useState<string | null>(null);
  const [isSavingEdit, setIsSavingEdit] = useState(false);
  
  // New Hypothesis Form State
  const [isCreating, setIsCreating] = useState(false);
  const [newHypothesisText, setNewHypothesisText] = useState('');
  const [newDescription, setNewDescription] = useState('');
  const [newReferenceUrl, setNewReferenceUrl] = useState('');
  const [newReferenceType, setNewReferenceType] = useState('');
  const [createError, setCreateError] = useState<string | null>(null);

  useEffect(() => {
    fetchHypotheses();
  }, []);

  const fetchHypotheses = async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/hypotheses');
      if (!res.ok) throw new Error('Failed to fetch hypotheses');
      const data = await res.json();
      setHypotheses(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  const handleCreateHypothesis = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newHypothesisText.trim()) {
      setCreateError('Hypothesis text is required');
      return;
    }
    setCreateError(null);
    try {
      const res = await fetch('http://127.0.0.1:8000/hypotheses', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          hypothesis_text: newHypothesisText.trim(),
          description: newDescription.trim() || null,
          reference_url: newReferenceUrl.trim() || null,
          reference_type: newReferenceType || null
        }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Failed to create hypothesis');
      }

      // Success: Reset form and refresh list
      setNewHypothesisText('');
      setNewDescription('');
      setNewReferenceUrl('');
      setNewReferenceType('');
      setIsCreating(false);
      fetchHypotheses();
    } catch (err: unknown) {
      setCreateError(err instanceof Error ? err.message : String(err));
    }
  };

  const handleDeleteHypothesis = async (hypothesisId: string, hypothesisText: string) => {
    // First confirmation
    const confirmFirst = window.confirm(
      `Are you sure you want to delete this hypothesis?\n\n"${hypothesisText.slice(0, 100)}${hypothesisText.length > 100 ? '...' : ''}"\n\nThis will also delete all associated evidence.`
    );
    
    if (!confirmFirst) return;
    
    // Second confirmation
    const confirmSecond = window.confirm(
      'This action cannot be undone. Are you absolutely sure you want to delete this hypothesis and all its evidence?'
    );
    
    if (!confirmSecond) return;
    
    try {
      const res = await fetch(`http://127.0.0.1:8000/hypotheses/${hypothesisId}`, {
        method: 'DELETE',
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Failed to delete hypothesis');
      }

      // Success: Refresh list
      fetchHypotheses();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      alert(`Failed to delete hypothesis: ${message}`);
    }
  };

  const startEdit = (hyp: HypothesisView) => {
    setEditError(null);
    setEditingHypothesisId(hyp.hypothesis_id);
    setEditHypothesisText(hyp.hypothesis_text || '');
    setEditDescription(hyp.description || '');
  };

  const cancelEdit = () => {
    setEditError(null);
    setEditingHypothesisId(null);
    setEditHypothesisText('');
    setEditDescription('');
  };

  const handleSaveEdit = async (hypothesisId: string) => {
    setEditError(null);
    const trimmed = editHypothesisText.trim();
    if (!trimmed) {
      setEditError('Hypothesis text is required');
      return;
    }

    setIsSavingEdit(true);
    try {
      const res = await fetch(`http://127.0.0.1:8000/hypotheses/${hypothesisId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          hypothesis_text: trimmed,
          description: editDescription.trim() || null,
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || 'Failed to update hypothesis');
      }

      cancelEdit();
      fetchHypotheses();
    } catch (err: unknown) {
      setEditError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsSavingEdit(false);
    }
  };

  if (loading) return <div className="p-8">Loading hypotheses...</div>;
  if (error) return <div className="p-8 text-red-600">Error: {error}</div>;

  return (
    <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
      <div className="px-4 py-6 sm:px-0">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-2xl font-bold text-gray-900">Hypotheses</h1>
          <button
            onClick={() => setIsCreating(!isCreating)}
            className="px-4 py-2 bg-indigo-600 text-white rounded hover:bg-indigo-700"
          >
            {isCreating ? 'Cancel' : 'Create New Hypothesis'}
          </button>
        </div>

        {/* Create Hypothesis Form */}
        {isCreating && (
          <div className="mb-8 bg-white p-6 rounded-lg shadow border border-gray-200">
            <h2 className="text-lg font-medium mb-4">Create New Hypothesis</h2>
            <form onSubmit={handleCreateHypothesis} className="space-y-4">
              <div>
                <label htmlFor="hypothesisText" className="block text-sm font-medium text-gray-700 mb-1">
                  Hypothesis Text *
                </label>
                <textarea
                  id="hypothesisText"
                  value={newHypothesisText}
                  onChange={(e) => setNewHypothesisText(e.target.value)}
                  rows={3}
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border text-gray-900"
                  placeholder="e.g., Google is falling behind OpenAI in the AI race"
                />
              </div>
              <div>
                <label htmlFor="description" className="block text-sm font-medium text-gray-700 mb-1">
                  Description / Context (Optional)
                </label>
                <textarea
                  id="description"
                  value={newDescription}
                  onChange={(e) => setNewDescription(e.target.value)}
                  rows={4}
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border text-gray-900"
                  placeholder="Multi-paragraph summary of core arguments (3-5 paragraphs for complex papers)"
                />
              </div>
              <div>
                <label htmlFor="referenceUrl" className="block text-sm font-medium text-gray-700 mb-1">
                  Reference URL (Optional)
                </label>
                <input
                  type="url"
                  id="referenceUrl"
                  value={newReferenceUrl}
                  onChange={(e) => setNewReferenceUrl(e.target.value)}
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border text-gray-900"
                  placeholder="https://example.com/paper.pdf"
                />
              </div>
              <div>
                <label htmlFor="referenceType" className="block text-sm font-medium text-gray-700 mb-1">
                  Reference Type (Optional)
                </label>
                <select
                  id="referenceType"
                  value={newReferenceType}
                  onChange={(e) => setNewReferenceType(e.target.value)}
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border text-gray-900"
                >
                  <option value="">-- Select Type --</option>
                  <option value="paper">Paper</option>
                  <option value="article">Article</option>
                  <option value="book">Book</option>
                  <option value="website">Website</option>
                </select>
              </div>
              {createError && <p className="text-sm text-red-600">{createError}</p>}
              <div className="flex justify-end">
                <button
                  type="submit"
                  className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700"
                >
                  Create
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Hypotheses List */}
        <div className="bg-white shadow overflow-hidden sm:rounded-lg">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th scope="col" className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
                <th scope="col" className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Hypothesis
                </th>
                <th scope="col" className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-20">
                  Description
                </th>
                <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-24">
                  Evidence
                </th>
                <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Latest Segment
                </th>
                <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-28">
                  Last Updated
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {hypotheses.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-4 text-center text-sm text-gray-500">
                    No hypotheses found. Create one to get started.
                  </td>
                </tr>
              ) : (
                hypotheses.map((hyp) => (
                  <tr key={hyp.hypothesis_id} className="hover:bg-gray-50">
                    <td className="px-3 py-4">
                      <div className="flex gap-2">
                        <Link
                          href={`/hypotheses/${hyp.hypothesis_id}/evidence`}
                          className="inline-flex items-center justify-center px-3 py-1.5 text-xs font-semibold text-white bg-indigo-600 rounded-md shadow-sm hover:bg-indigo-700 active:bg-indigo-800 transition-all"
                        >
                          View Evidence
                        </Link>
                        {editingHypothesisId === hyp.hypothesis_id ? (
                          <>
                            <button
                              onClick={() => handleSaveEdit(hyp.hypothesis_id)}
                              disabled={isSavingEdit}
                              className="inline-flex items-center justify-center px-3 py-1.5 text-xs font-semibold text-white bg-green-600 rounded-md shadow-sm hover:bg-green-700 active:bg-green-800 disabled:bg-green-300 disabled:cursor-not-allowed transition-all"
                              title="Save changes"
                            >
                              {isSavingEdit ? 'Saving...' : 'Save'}
                            </button>
                            <button
                              onClick={cancelEdit}
                              disabled={isSavingEdit}
                              className="inline-flex items-center justify-center px-3 py-1.5 text-xs font-semibold text-gray-700 bg-gray-100 rounded-md shadow-sm hover:bg-gray-200 active:bg-gray-300 disabled:bg-gray-50 disabled:cursor-not-allowed transition-all"
                              title="Cancel editing"
                            >
                              Cancel
                            </button>
                          </>
                        ) : (
                          <button
                            onClick={() => startEdit(hyp)}
                            className="inline-flex items-center justify-center px-3 py-1.5 text-xs font-semibold text-white bg-blue-600 rounded-md shadow-sm hover:bg-blue-700 active:bg-blue-800 transition-all"
                            title="Edit hypothesis"
                          >
                            Edit
                          </button>
                        )}
                        <button
                          onClick={() => handleDeleteHypothesis(hyp.hypothesis_id, hyp.hypothesis_text || 'Untitled')}
                          className="inline-flex items-center justify-center px-3 py-1.5 text-xs font-semibold text-white bg-red-600 rounded-md shadow-sm hover:bg-red-700 active:bg-red-800 transition-all"
                          title="Delete hypothesis and all evidence"
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                    <td className="px-3 py-4 text-sm font-medium text-gray-900" style={{ maxWidth: '400px' }}>
                      <div className="flex items-start gap-2">
                        <div className="flex-1">
                          {editingHypothesisId === hyp.hypothesis_id ? (
                            <div className="space-y-2">
                              <textarea
                                value={editHypothesisText}
                                onChange={(e) => setEditHypothesisText(e.target.value)}
                                rows={3}
                                className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border text-gray-900"
                              />
                              <textarea
                                value={editDescription}
                                onChange={(e) => setEditDescription(e.target.value)}
                                rows={3}
                                className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border text-gray-900"
                                placeholder="Description (optional)"
                              />
                              {editError && <p className="text-xs text-red-600">{editError}</p>}
                            </div>
                          ) : (
                            (hyp.hypothesis_text
                              ? (hyp.hypothesis_text.length > 150
                                  ? hyp.hypothesis_text.substring(0, 150) + '...'
                                  : hyp.hypothesis_text)
                              : '-')
                          )}
                        </div>
                        {hyp.reference_url && (
                          <a 
                            href={hyp.reference_url} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            className="flex-shrink-0 text-blue-600 hover:text-blue-800"
                            title={`View ${hyp.reference_type || 'reference'}`}
                          >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                            </svg>
                          </a>
                        )}
                      </div>
                      {hyp.reference_type && (
                        <span className="inline-block mt-1 px-2 py-0.5 text-xs rounded bg-purple-100 text-purple-800">
                          {hyp.reference_type}
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-4 text-sm text-gray-700 max-w-[120px] break-words">
                      {hyp.description 
                        ? (hyp.description.length > 75 
                            ? hyp.description.substring(0, 75) + '...' 
                            : hyp.description)
                        : '-'}
                    </td>
                    <td className="px-4 py-4 text-sm text-gray-700">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                        {hyp.evidence_count} segment{hyp.evidence_count !== 1 ? 's' : ''}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-sm text-gray-700 break-words" style={{ minWidth: '250px', maxWidth: '350px' }}>
                      {hyp.latest_document_title ? (
                        <div>
                          <div className="font-medium text-gray-900 mb-1">{hyp.latest_document_title}</div>
                          {hyp.latest_segment_text_preview && (
                            <div className="text-xs text-gray-600 mt-1 break-words">
                              {hyp.latest_segment_text_preview.slice(0, 100)}...
                            </div>
                          )}
                        </div>
                      ) : hyp.latest_segment_id ? (
                        <div className="text-gray-500 text-xs">
                          Segment: {hyp.latest_segment_id.substring(0, 8)}...
                        </div>
                      ) : (
                        <span className="text-gray-400">No evidence yet</span>
                      )}
                    </td>
                    <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-500">
                      {new Date(hyp.last_updated_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </main>
  );
}
