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
  const [documents, setDocuments] = useState<DocumentList[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [archiving, setArchiving] = useState<string | null>(null);

  useEffect(() => {
    fetchDocuments();
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

  if (loading) return <div className="p-8">Loading documents...</div>;
  if (error) return <div className="p-8 text-red-600">Error: {error}</div>;

  return (
    <main className="w-full px-4 py-6 lg:px-8">
      <div className="py-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">Documents</h1>
        <div className="bg-white shadow overflow-x-auto sm:rounded-lg">
          <table className="w-full divide-y divide-gray-200">
            <colgroup>
              <col className="w-[110px]" />
              <col className="w-[180px]" />
              <col className="w-[120px]" />
              <col className="w-[80px]" />
              <col className="w-[50px]" />
              <col />
            </colgroup>
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
                        className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-medium ${
                          doc.segment_count > 0 ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'
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
