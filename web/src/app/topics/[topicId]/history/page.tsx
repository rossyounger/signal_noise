'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';

interface TopicHistoryEntry {
  topic_id: string;
  segment_id: string;
  name: string;
  description: string | null;
  user_hypothesis: string | null;
  summary_text: string | null;
  created_at: string;
  segment_text_preview: string | null;
  document_id: string | null;
  document_title: string | null;
}

export default function TopicHistoryPage() {
  const params = useParams();
  const topicId = params.topicId as string;
  const [history, setHistory] = useState<TopicHistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!topicId) return;
    fetchTopicHistory();
  }, [topicId]);

  const fetchTopicHistory = async () => {
    try {
      const res = await fetch(`http://127.0.0.1:8000/topics/${topicId}/history`);
      if (!res.ok) throw new Error('Failed to fetch topic history');
      const data = await res.json();
      setHistory(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div className="p-8">Loading topic history...</div>;
  if (error) return <div className="p-8 text-red-600">Error: {error}</div>;

  return (
    <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
      <div className="px-4 py-6 sm:px-0">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900">Topic History</h1>
          <p className="mt-1 text-sm text-gray-500">
            Full history of topic analysis across all segments, sorted by last update date
          </p>
        </div>

        {/* Topic History Table */}
        <div className="bg-white shadow overflow-hidden sm:rounded-lg">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th scope="col" className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-32">
                  Name
                </th>
                <th scope="col" className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-20">
                  Description
                </th>
                <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Hypotheses
                </th>
                <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  AI Analysis
                </th>
                <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Segment
                </th>
                <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-28">
                  Last Updated
                </th>
                <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-32">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {history.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-4 text-center text-sm text-gray-500">
                    No history found for this topic.
                  </td>
                </tr>
              ) : (
                history.map((entry) => (
                  <tr key={`${entry.topic_id}-${entry.segment_id}-${entry.created_at}`} className="hover:bg-gray-50">
                    <td className="px-3 py-4 text-sm font-medium text-indigo-600">
                      {entry.name || '-'}
                    </td>
                    <td className="px-3 py-4 text-sm text-gray-700 max-w-[80px] break-words">
                      {entry.description 
                        ? (entry.description.length > 75 
                            ? entry.description.substring(0, 75) + '...' 
                            : entry.description)
                        : '-'}
                    </td>
                    <td className="px-4 py-4 text-sm text-gray-700 break-words whitespace-pre-line" style={{ minWidth: '400px', maxWidth: '500px' }}>
                      {entry.user_hypothesis || '-'}
                    </td>
                    <td className="px-4 py-4 text-sm text-gray-700 break-words whitespace-pre-line" style={{ minWidth: '400px', maxWidth: '500px' }}>
                      {entry.summary_text || '-'}
                    </td>
                    <td className="px-4 py-4 text-sm text-gray-700 break-words" style={{ minWidth: '350px', maxWidth: '450px' }}>
                      {entry.document_title ? (
                        <div>
                          <div className="font-medium text-gray-900 mb-1">{entry.document_title}</div>
                          {entry.segment_text_preview && (
                            <div className="text-xs text-gray-600 mt-1 break-words">
                              {entry.segment_text_preview}
                            </div>
                          )}
                        </div>
                      ) : entry.segment_id ? (
                        <div className="text-gray-500 text-xs">
                          Segment: {entry.segment_id.substring(0, 8)}... (document may be deleted)
                        </div>
                      ) : (
                        <span className="text-gray-400">No segment linked</span>
                      )}
                    </td>
                    <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-500">
                      {new Date(entry.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-4">
                      <Link
                        href={`/segments/${entry.segment_id}/analyze`}
                        className="inline-flex items-center justify-center px-3 py-1.5 text-xs font-semibold text-white bg-indigo-600 rounded-md shadow-sm hover:bg-indigo-700 active:bg-indigo-800 transition-all"
                      >
                        Edit Segment
                      </Link>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
          </div>
        </div>
      </div>
    </main>
  );
}

