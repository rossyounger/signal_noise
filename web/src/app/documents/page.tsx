'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';

interface DocumentList {
  id: string;
  source_title: string | null;
  title: string | null;
  author: string | null;
  published_at: string | null;
  created_at: string;
  content_text_preview: string | null;
  original_url: string | null;
  segment_count: number;
}

export default function DocumentsPage() {
  // ... (URL ingestion state if any, but we are in documents page)
  const [documents, setDocuments] = useState<DocumentList[]>([]);
  const [sources, setSources] = useState<{ id: string; name: string | null }[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingDoc, setEditingDoc] = useState<DocumentList | null>(null);
  const [editForm, setEditForm] = useState({ title: '', author: '', published_at: '', source_id: '' });
  const [archiving, setArchiving] = useState<string | null>(null);

  useEffect(() => {
    fetchDocuments();
    fetchSources();
  }, []);

  const fetchDocuments = async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/documents');
      if (!res.ok) throw new Error('Failed to fetch documents');
      const data = await res.json();
      setDocuments(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchSources = async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/sources');
      if (res.ok) {
        const data = await res.json();
        setSources(data);
      }
    } catch (err) {
      console.error('Failed to fetch sources', err);
    }
  };

  const handleArchive = async (documentId: string) => {
    if (!confirm('Are you sure you want to archive this document? It will be hidden from the list.')) {
      return;
    }

    setArchiving(documentId);
    try {
      const res = await fetch(`http://127.0.0.1:8000/documents/${documentId}/archive`, {
        method: 'PATCH',
      });
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to archive document');
      }
      // Remove from local state
      setDocuments((prev) => prev.filter((d) => d.id !== documentId));
    } catch (err: any) {
      alert(`Error: ${err.message}`);
    } finally {
      setArchiving(null);
    }
  };

  const handleEdit = (doc: DocumentList) => {
    setEditingDoc(doc);
    // Find the source_id that corresponds to the doc's source_title if possible?
    // Actually the document object in the list doesn't include source_id, only source_title.
    // We strictly need source_id on the document object to pre-fill the select correctly.
    // Limitation: LIST endpoint doesn't return source_id.
    // Workaround: We default to empty (no change) or try to match by name?
    // Better: Update LIST endpoint to return source_id? 
    // Wait, let's just default to "No Change" (empty string) effectively.
    // If they want to change it, they select a new one.
    // BUT user experience: if I open edit, I expect to see the current source selected.
    // I need to add `source_id` to DocumentList schema in frontend and backend.

    // Assuming for now I can't easily change backend list schema without another step.
    // Use what we have. If source_title matches a source name, use that ID.
    const matchedSource = sources.find(s => s.name === doc.source_title);
    setEditForm({
      title: doc.title || '',
      author: doc.author || '',
      published_at: doc.published_at ? new Date(doc.published_at).toISOString().split('T')[0] : '',
      source_id: matchedSource ? matchedSource.id : '',
    });
  };

  const handleSaveEdit = async () => {
    if (!editingDoc) return;

    try {
      const res = await fetch(`http://127.0.0.1:8000/documents/${editingDoc.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: editForm.title || null,
          author: editForm.author || null,
          published_at: editForm.published_at ? new Date(editForm.published_at).toISOString() : null,
          source_id: editForm.source_id || null,
        }),
      });

      if (!res.ok) {
        throw new Error('Failed to update document');
      }

      const updatedDoc = await res.json();
      setDocuments((prev) => prev.map((d) => (d.id === updatedDoc.id ? updatedDoc : d)));
      setEditingDoc(null);
    } catch (err: any) {
      alert(`Error saving: ${err.message}`);
    }
  };

  // ... (rendering)

  return (
    <main className="w-full px-4 py-6 lg:px-8">
      {/* Edit Modal */}
      {editingDoc && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white p-6 rounded-lg shadow-xl w-full max-w-md">
            <h2 className="text-xl font-bold mb-4">Edit Document</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700">Title</label>
                <input
                  type="text"
                  value={editForm.title}
                  onChange={(e) => setEditForm({ ...editForm, title: e.target.value })}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm text-gray-900 border p-2"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Source</label>
                <select
                  value={editForm.source_id}
                  onChange={(e) => setEditForm({ ...editForm, source_id: e.target.value })}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:border-indigo-500 sm:text-sm text-gray-900 border p-2"
                >
                  <option value="">(No Source)</option>
                  {sources.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name || 'Untitled Source'}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Author</label>
                <input
                  type="text"
                  value={editForm.author}
                  onChange={(e) => setEditForm({ ...editForm, author: e.target.value })}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm text-gray-900 border p-2"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Published Date</label>
                <input
                  type="date"
                  value={editForm.published_at}
                  onChange={(e) => setEditForm({ ...editForm, published_at: e.target.value })}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm text-gray-900 border p-2"
                />
              </div>
            </div>
            <div className="mt-6 flex justify-end gap-3">
              <button
                onClick={() => setEditingDoc(null)}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveEdit}
                className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-md hover:bg-indigo-700"
              >
                Save Changes
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="py-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">Documents</h1>
        <div className="bg-white shadow overflow-x-auto sm:rounded-lg">
          <table className="w-full divide-y divide-gray-200">
            {/* ... Columns ... */}
            <colgroup>
              <col className="w-[140px]" />
              <col className="w-[180px]" />
            </colgroup>
            {/* ... Thead ... */}
            <thead className="bg-gray-50">
              <tr>
                <th scope="col" className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
                <th scope="col" className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Article
                </th>
                <th scope="col" className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Author
                </th>
                <th scope="col" className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Date
                </th>
                <th scope="col" className="px-3 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Seg
                </th>
                <th scope="col" className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Preview
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {documents.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-4 text-center text-sm text-gray-500">
                    No documents found.
                  </td>
                </tr>
              ) : (
                documents.map((doc) => (
                  <tr key={doc.id} className="hover:bg-gray-50 align-top">
                    <td className="px-3 py-3">
                      <div className="flex flex-col gap-1.5">
                        <Link
                          href={`/documents/${doc.id}/segmentation`}
                          className="inline-flex items-center justify-center px-3 py-1.5 text-xs font-semibold text-white bg-indigo-600 rounded-md shadow-sm hover:bg-indigo-700 active:bg-indigo-800 transition-all"
                        >
                          Segment
                        </Link>
                        <Link
                          href={`/documents/${doc.id}/transcription`}
                          className="inline-flex items-center justify-center px-3 py-1.5 text-xs font-semibold text-white bg-purple-600 rounded-md shadow-sm hover:bg-purple-700 active:bg-purple-800 transition-all"
                        >
                          Transcribe
                        </Link>
                        <button
                          onClick={() => handleEdit(doc)}
                          className="inline-flex items-center justify-center px-3 py-1.5 text-xs font-semibold text-gray-700 bg-white border border-gray-300 rounded-md shadow-sm hover:bg-gray-50 transition-all"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => handleArchive(doc.id)}
                          disabled={archiving === doc.id}
                          className="inline-flex items-center justify-center px-3 py-1.5 text-xs font-semibold text-gray-700 bg-gray-100 border border-gray-300 rounded-md shadow-sm hover:bg-gray-200 active:bg-gray-300 transition-all disabled:opacity-50"
                        >
                          {archiving === doc.id ? '...' : 'Archive'}
                        </button>
                      </div>
                    </td>
                    <td className="px-3 py-3">
                      {doc.original_url ? (
                        <a
                          href={doc.original_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm font-medium text-indigo-600 hover:text-indigo-800 hover:underline line-clamp-2"
                          title={doc.title || 'Untitled'}
                        >
                          {doc.title || 'Untitled'}
                        </a>
                      ) : (
                        <div className="text-sm font-medium text-gray-900 line-clamp-2" title={doc.title || 'Untitled'}>
                          {doc.title || 'Untitled'}
                        </div>
                      )}
                      <div className="text-xs text-gray-500 truncate">{doc.source_title || 'Unknown Source'}</div>
                    </td>
                    <td className="px-3 py-3 text-sm text-gray-500">
                      <span className="line-clamp-2">{doc.author || '-'}</span>
                    </td>
                    <td className="px-3 py-3 text-xs text-gray-500">
                      {doc.published_at ? new Date(doc.published_at).toLocaleDateString() : '-'}
                    </td>
                    <td className="px-3 py-3 text-center">
                      <span
                        className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-medium ${doc.segment_count > 0 ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'
                          }`}
                      >
                        {doc.segment_count}
                      </span>
                    </td>
                    <td className="px-3 py-3 text-xs text-gray-600">
                      <div className="line-clamp-3 leading-relaxed">{doc.content_text_preview || '-'}</div>
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
