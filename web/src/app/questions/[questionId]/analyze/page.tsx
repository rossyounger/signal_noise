'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';

interface QuestionHypothesis {
  hypothesis_id: string;
  hypothesis_text: string | null;
  description: string | null;
  reference_url: string | null;
  reference_type: string | null;
  evidence_count: number;
  created_at: string;
}

interface AvailableHypothesis {
  hypothesis_id: string;
  hypothesis_text: string | null;
  description: string | null;
  reference_url: string | null;
  reference_type: string | null;
}

export default function QuestionAnalyzePage() {
  const params = useParams();
  const questionId = params.questionId as string;

  const [questionText, setQuestionText] = useState<string>('');
  const [linkedHypotheses, setLinkedHypotheses] = useState<QuestionHypothesis[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modal State
  const [isHypothesisModalOpen, setHypothesisModalOpen] = useState(false);
  const [availableHypotheses, setAvailableHypotheses] = useState<AvailableHypothesis[]>([]);
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    if (!questionId) return;
    fetchQuestionData();
  }, [questionId]);

  const fetchQuestionData = async () => {
    try {
      // Fetch question details
      const questionRes = await fetch(`http://127.0.0.1:8000/questions`);
      if (!questionRes.ok) throw new Error('Failed to fetch questions');
      const allQuestions = await questionRes.json();
      const question = allQuestions.find((q: any) => q.question_id === questionId);
      if (question) {
        setQuestionText(question.question_text);
      }

      // Fetch linked hypotheses
      const hypothesesRes = await fetch(`http://127.0.0.1:8000/questions/${questionId}/hypotheses`);
      if (!hypothesesRes.ok) throw new Error('Failed to fetch linked hypotheses');
      const hypothesesData = await hypothesesRes.json();
      setLinkedHypotheses(hypothesesData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An unknown error occurred');
    } finally {
      setIsLoading(false);
    }
  };

  const fetchAvailableHypotheses = async () => {
    try {
      const response = await fetch('http://127.0.0.1:8000/hypotheses');
      if (!response.ok) throw new Error('Failed to fetch available hypotheses.');
      const data = await response.json();
      setAvailableHypotheses(data.map((h: any) => ({
        hypothesis_id: h.hypothesis_id,
        hypothesis_text: h.hypothesis_text,
        description: h.description,
        reference_url: h.reference_url,
        reference_type: h.reference_type,
      })));
    } catch (err) {
      console.error('Error fetching available hypotheses:', err);
      alert('Failed to load available hypotheses for linking.');
    }
  };

  const handleLinkExisting = () => {
    setHypothesisModalOpen(true);
    fetchAvailableHypotheses();
  };

  const handleSelectHypothesis = async (hyp: AvailableHypothesis) => {
    // Check if this hypothesis is already linked
    const isAlreadyLinked = linkedHypotheses.some(h => h.hypothesis_id === hyp.hypothesis_id);

    if (isAlreadyLinked) {
      alert('This hypothesis is already linked to this question.');
      setHypothesisModalOpen(false);
      return;
    }

    try {
      const res = await fetch(`http://127.0.0.1:8000/questions/${questionId}/hypotheses`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ hypothesis_id: hyp.hypothesis_id }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Failed to link hypothesis');
      }

      // Success: Refresh the list
      setHypothesisModalOpen(false);
      fetchQuestionData();
    } catch (err: any) {
      alert(`Failed to link hypothesis: ${err.message}`);
    }
  };

  const filteredHypotheses = availableHypotheses.filter(hyp =>
    hyp.hypothesis_text?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    hyp.description?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  if (isLoading) return <div className="p-12 text-center">Loading question data...</div>;
  if (error) return <div className="p-12 text-center text-red-500">Error: {error}</div>;

  return (
    <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
      <div className="px-4 py-6 sm:px-0">
        {/* Header */}
        <div className="mb-6">
          <Link href="/questions" className="text-sm text-indigo-600 hover:text-indigo-800 mb-2 inline-block">
            ← Back to Questions
          </Link>
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Analyze Question</h1>
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <p className="text-lg text-gray-900">{questionText}</p>
          </div>
        </div>

        {/* Action Bar */}
        <div className="mb-6 flex justify-end">
          <button
            onClick={handleLinkExisting}
            className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded shadow-sm hover:bg-indigo-700 transition-colors"
          >
            Link Existing Hypothesis
          </button>
        </div>

        {/* Linked Hypotheses */}
        <div className="bg-white shadow overflow-hidden sm:rounded-lg">
          <div className="px-4 py-5 sm:px-6 border-b border-gray-200">
            <h2 className="text-lg font-medium text-gray-900">Linked Hypotheses</h2>
            <p className="mt-1 text-sm text-gray-500">
              Hypotheses that help answer this question
            </p>
          </div>
          
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Hypothesis
                </th>
                <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-32">
                  Evidence
                </th>
                <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-32">
                  Linked
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {linkedHypotheses.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-6 py-8 text-center text-sm text-gray-500">
                    No hypotheses linked yet. Click &quot;Link Existing Hypothesis&quot; to add one.
                  </td>
                </tr>
              ) : (
                linkedHypotheses.map((hyp) => (
                  <tr key={hyp.hypothesis_id} className="hover:bg-gray-50">
                    <td className="px-6 py-4">
                      <Link
                        href={`/hypotheses/${hyp.hypothesis_id}/evidence`}
                        className="inline-flex items-center justify-center px-3 py-1.5 text-xs font-semibold text-white bg-indigo-600 rounded-md shadow-sm hover:bg-indigo-700 active:bg-indigo-800 transition-all"
                      >
                        View Evidence
                      </Link>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-900">
                      <div className="flex items-start gap-2">
                        <div className="flex-1">
                          <div className="font-medium">
                            {hyp.hypothesis_text 
                              ? (hyp.hypothesis_text.length > 120 
                                  ? hyp.hypothesis_text.substring(0, 120) + '...' 
                                  : hyp.hypothesis_text)
                              : 'Untitled Hypothesis'}
                          </div>
                          {hyp.description && (
                            <div className="text-xs text-gray-600 mt-1">
                              {hyp.description.length > 150 
                                ? hyp.description.substring(0, 150) + '...' 
                                : hyp.description}
                            </div>
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
                    <td className="px-4 py-4 text-sm text-gray-700">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                        {hyp.evidence_count} segment{hyp.evidence_count !== 1 ? 's' : ''}
                      </span>
                    </td>
                    <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-500">
                      {new Date(hyp.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Hypothesis Selection Modal */}
      {isHypothesisModalOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[80vh] flex flex-col">
            <div className="p-4 border-b flex justify-between items-center">
              <h3 className="text-lg font-bold text-gray-800">Link Existing Hypothesis</h3>
              <button onClick={() => setHypothesisModalOpen(false)} className="text-gray-500 hover:text-gray-700">✕</button>
            </div>

            <div className="p-4 border-b">
              <input
                type="text"
                placeholder="Search hypotheses..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full px-3 py-2 border rounded text-gray-900"
              />
            </div>

            <div className="p-4 flex-1 overflow-y-auto">
              {filteredHypotheses.length === 0 ? (
                <div className="text-center text-gray-500 py-8">
                  {searchTerm ? 'No hypotheses match your search.' : 'Loading hypotheses...'}
                </div>
              ) : (
                <div className="divide-y">
                  {filteredHypotheses.map(hyp => (
                    <div
                      key={hyp.hypothesis_id}
                      className="py-3 px-2 hover:bg-gray-50 cursor-pointer group flex justify-between items-center"
                      onClick={() => handleSelectHypothesis(hyp)}
                    >
                      <div>
                        <div className="font-medium text-gray-800 flex items-center gap-2">
                          <span>
                            {(hyp.hypothesis_text || 'Untitled Hypothesis').slice(0, 80)}
                            {(hyp.hypothesis_text || '').length > 80 && '...'}
                          </span>
                          {hyp.reference_url && (
                            <span className="text-purple-600 text-xs px-1.5 py-0.5 bg-purple-100 rounded">
                              {hyp.reference_type || 'ref'}
                            </span>
                          )}
                        </div>
                        {hyp.description && (
                          <div className="text-sm text-gray-500 line-clamp-1">{hyp.description}</div>
                        )}
                      </div>
                      <button className="text-indigo-600 font-medium text-sm px-3 py-1 rounded bg-indigo-50 hover:bg-indigo-100 opacity-0 group-hover:opacity-100 transition-opacity">
                        Select
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
