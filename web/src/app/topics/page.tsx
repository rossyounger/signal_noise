'use client';

import { useState, useEffect } from 'react';

interface TopicHomeView {
  topic_id: string;
  latest_name: string;
  latest_description: string | null;
  latest_user_hypothesis: string | null;
  last_updated_at: string;
  segment_id: string | null;
  segment_text_preview: string | null;
  document_id: string | null;
  document_title: string | null;
}

export default function TopicsPage() {
  const [topics, setTopics] = useState<TopicHomeView[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // New Topic Form State
  const [isCreating, setIsCreating] = useState(false);
  const [newTopicName, setNewTopicName] = useState('');
  const [createError, setCreateError] = useState<string | null>(null);

  useEffect(() => {
    fetchTopics();
  }, []);

  const fetchTopics = async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/topics');
      if (!res.ok) throw new Error('Failed to fetch topics');
      const data = await res.json();
      setTopics(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateTopic = async (e: React.FormEvent) => {
    e.preventDefault();
    // Name is optional - topic will get its name when first saved to history with a segment
    setCreateError(null);
    try {
      const res = await fetch('http://127.0.0.1:8000/topics', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newTopicName.trim() || null }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Failed to create topic');
      }

      // Success: Reset form and refresh list
      setNewTopicName('');
      setIsCreating(false);
      fetchTopics();
    } catch (err: any) {
      setCreateError(err.message);
    }
  };

  if (loading) return <div className="p-8">Loading topics...</div>;
  if (error) return <div className="p-8 text-red-600">Error: {error}</div>;

  return (
    <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
      <div className="px-4 py-6 sm:px-0">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-2xl font-bold text-gray-900">Topics</h1>
          <button
            onClick={() => setIsCreating(!isCreating)}
            className="px-4 py-2 bg-indigo-600 text-white rounded hover:bg-indigo-700"
          >
            {isCreating ? 'Cancel' : 'Create New Topic'}
          </button>
        </div>

        {/* Create Topic Form */}
        {isCreating && (
          <div className="mb-8 bg-white p-6 rounded-lg shadow border border-gray-200">
            <h2 className="text-lg font-medium mb-4">Create New Topic</h2>
            <form onSubmit={handleCreateTopic} className="flex gap-4 items-start">
              <div className="flex-1">
                <label htmlFor="topicName" className="block text-sm font-medium text-gray-700 mb-1">
                  Topic Name (Optional)
                </label>
                <input
                  type="text"
                  id="topicName"
                  value={newTopicName}
                  onChange={(e) => setNewTopicName(e.target.value)}
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border text-gray-900"
                  placeholder="e.g. Artificial General Intelligence (optional)"
                />
                <p className="mt-1 text-xs text-gray-500">
                  Topic name will be set when you first save it to a segment's analysis.
                </p>
                {createError && <p className="mt-2 text-sm text-red-600">{createError}</p>}
              </div>
              <button
                type="submit"
                className="mt-6 px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700"
              >
                Create
              </button>
            </form>
          </div>
        )}

        {/* Topics List */}
        <div className="bg-white shadow overflow-hidden sm:rounded-lg">
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
                  Latest Hypothesis
                </th>
                <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Document / Segment
                </th>
                <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-28">
                  Last Updated
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {topics.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-6 py-4 text-center text-sm text-gray-500">
                    No topics found. Create one to get started.
                  </td>
                </tr>
              ) : (
                topics.map((topic) => (
                  <tr key={topic.topic_id} className="hover:bg-gray-50">
                    <td className="px-3 py-4 text-sm font-medium text-indigo-600">
                      {topic.latest_name || '-'}
                    </td>
                    <td className="px-3 py-4 text-sm text-gray-700 max-w-[80px] break-words">
                      {topic.latest_description 
                        ? (topic.latest_description.length > 75 
                            ? topic.latest_description.substring(0, 75) + '...' 
                            : topic.latest_description)
                        : '-'}
                    </td>
                    <td className="px-4 py-4 text-sm text-gray-700 break-words whitespace-pre-line" style={{ minWidth: '400px', maxWidth: '500px' }}>
                      {topic.latest_user_hypothesis || '-'}
                    </td>
                    <td className="px-4 py-4 text-sm text-gray-700 break-words" style={{ minWidth: '350px', maxWidth: '450px' }}>
                      {topic.document_title ? (
                        <div>
                          <div className="font-medium text-gray-900 mb-1">{topic.document_title}</div>
                          {topic.segment_text_preview && (
                            <div className="text-xs text-gray-600 mt-1 break-words">
                              {topic.segment_text_preview}
                            </div>
                          )}
                        </div>
                      ) : topic.segment_id ? (
                        <div className="text-gray-500 text-xs">
                          Segment: {topic.segment_id.substring(0, 8)}... (document may be deleted)
                        </div>
                      ) : (
                        <span className="text-gray-400">No segment linked</span>
                      )}
                    </td>
                    <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-500">
                      {new Date(topic.last_updated_at).toLocaleDateString()}
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


