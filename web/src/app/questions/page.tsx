'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';

interface Question {
  question_id: string;
  question_text: string;
  created_at: string;
  hypothesis_count: number;
}

export default function QuestionsPage() {
  const [questions, setQuestions] = useState<Question[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // New Question Form State
  const [isCreating, setIsCreating] = useState(false);
  const [newQuestionText, setNewQuestionText] = useState('');
  const [createError, setCreateError] = useState<string | null>(null);

  useEffect(() => {
    fetchQuestions();
  }, []);

  const fetchQuestions = async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/questions');
      if (!res.ok) throw new Error('Failed to fetch questions');
      const data = await res.json();
      setQuestions(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateQuestion = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newQuestionText.trim()) {
      setCreateError('Question text is required');
      return;
    }
    setCreateError(null);
    try {
      const res = await fetch('http://127.0.0.1:8000/questions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          question_text: newQuestionText.trim()
        }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Failed to create question');
      }

      // Success: Reset form and refresh list
      setNewQuestionText('');
      setIsCreating(false);
      fetchQuestions();
    } catch (err: any) {
      setCreateError(err.message);
    }
  };

  const handleDeleteQuestion = async (questionId: string, questionText: string) => {
    // First confirmation
    const confirmFirst = window.confirm(
      `Are you sure you want to delete this question?\n\n"${questionText.slice(0, 100)}${questionText.length > 100 ? '...' : ''}"\n\nThis will remove all hypothesis links for this question (hypotheses themselves will not be affected).`
    );
    
    if (!confirmFirst) return;
    
    // Second confirmation
    const confirmSecond = window.confirm(
      'This action cannot be undone. Are you absolutely sure you want to delete this question?'
    );
    
    if (!confirmSecond) return;
    
    try {
      const res = await fetch(`http://127.0.0.1:8000/questions/${questionId}`, {
        method: 'DELETE',
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Failed to delete question');
      }

      // Success: Refresh list
      fetchQuestions();
    } catch (err: any) {
      alert(`Failed to delete question: ${err.message}`);
    }
  };

  if (loading) return <div className="p-8">Loading questions...</div>;
  if (error) return <div className="p-8 text-red-600">Error: {error}</div>;

  return (
    <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
      <div className="px-4 py-6 sm:px-0">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-2xl font-bold text-gray-900">Questions</h1>
          <button
            onClick={() => setIsCreating(!isCreating)}
            className="px-4 py-2 bg-indigo-600 text-white rounded hover:bg-indigo-700"
          >
            {isCreating ? 'Cancel' : 'Create New Question'}
          </button>
        </div>

        {/* Create Question Form */}
        {isCreating && (
          <div className="mb-8 bg-white p-6 rounded-lg shadow border border-gray-200">
            <h2 className="text-lg font-medium mb-4">Create New Question</h2>
            <form onSubmit={handleCreateQuestion} className="space-y-4">
              <div>
                <label htmlFor="questionText" className="block text-sm font-medium text-gray-700 mb-1">
                  Question Text *
                </label>
                <textarea
                  id="questionText"
                  value={newQuestionText}
                  onChange={(e) => setNewQuestionText(e.target.value)}
                  rows={3}
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border text-gray-900"
                  placeholder="e.g., How is AI development affecting software engineering practices?"
                />
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

        {/* Questions List */}
        <div className="bg-white shadow overflow-hidden sm:rounded-lg">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Question
                </th>
                <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-32">
                  Hypotheses
                </th>
                <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-32">
                  Created
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {questions.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-6 py-4 text-center text-sm text-gray-500">
                    No questions found. Create one to get started.
                  </td>
                </tr>
              ) : (
                questions.map((question) => (
                  <tr key={question.question_id} className="hover:bg-gray-50">
                    <td className="px-6 py-4">
                      <div className="flex gap-2">
                        <Link
                          href={`/questions/${question.question_id}/analyze`}
                          className="inline-flex items-center justify-center px-3 py-1.5 text-xs font-semibold text-white bg-indigo-600 rounded-md shadow-sm hover:bg-indigo-700 active:bg-indigo-800 transition-all"
                        >
                          Analyze Question
                        </Link>
                        <button
                          onClick={() => handleDeleteQuestion(question.question_id, question.question_text)}
                          className="inline-flex items-center justify-center px-3 py-1.5 text-xs font-semibold text-white bg-red-600 rounded-md shadow-sm hover:bg-red-700 active:bg-red-800 transition-all"
                          title="Delete question and its hypothesis links"
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm font-medium text-gray-900">
                      {question.question_text}
                    </td>
                    <td className="px-4 py-4 text-sm text-gray-700">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                        {question.hypothesis_count} linked
                      </span>
                    </td>
                    <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-500">
                      {new Date(question.created_at).toLocaleDateString()}
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
