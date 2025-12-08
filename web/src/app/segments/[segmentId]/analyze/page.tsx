"use client";

import { useEffect, useState, useMemo } from 'react';
import { useParams, useRouter } from 'next/navigation';
import ReactMarkdown from 'react-markdown';

// --- Type Definitions ---
type SegmentWorkbenchContent = {
  segment: { id: string; document_id: string; text: string; content_html: string | null; };
  document: { id: string; url: string; title: string; author: string | null; html_content: string | null; };
};

type TopicSuggestion = {
  topic_id?: string;
  name: string;
  source: 'existing' | 'generated';
  description?: string;
  user_hypothesis?: string;
  summary_text?: string;
};

// Represents a topic being edited, including its AI-generated POV
type StagedChange = TopicSuggestion & {
  pov_summary?: string;
  pov_id?: string;
  editingField?: 'description' | 'user_hypothesis' | null;
  isDirty?: boolean; // Track if user has modified this topic
  markedForSave?: boolean; // Explicitly marked for saving
};

// --- Page Component ---
export default function SegmentAnalyzePage() {
  const params = useParams();
  const router = useRouter();
  const segmentId = params.segmentId as string;

  // --- State Management ---
  const [workbenchData, setWorkbenchData] = useState<SegmentWorkbenchContent | null>(null);
  const [initialTopics, setInitialTopics] = useState<TopicSuggestion[]>([]);
  const [stagedChanges, setStagedChanges] = useState<Record<string, StagedChange>>({});
  const [activeTopicKey, setActiveTopicKey] = useState<string | null>(null);

  const [isLoading, setIsLoading] = useState(true);
  const [isGeneratingPov, setIsGeneratingPov] = useState(false);
  const [isCheckingHypothesis, setIsCheckingHypothesis] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Memoized derived state
  const activeEditingTopic = useMemo(() => {
    if (!activeTopicKey) return null;
    return stagedChanges[activeTopicKey];
  }, [activeTopicKey, stagedChanges]);

  // Count topics marked for save
  const topicsToSaveCount = useMemo(() => {
    return Object.values(stagedChanges).filter(t => t.markedForSave).length;
  }, [stagedChanges]);

  // --- Data Fetching ---
  useEffect(() => {
    if (!segmentId) return;
    const fetchData = async () => {
      try {
        const segmentRes = await fetch(`http://127.0.0.1:8000/segments/${segmentId}`);
        if (!segmentRes.ok) throw new Error('Failed to fetch segment details.');
        const segmentData: SegmentWorkbenchContent = await segmentRes.json();
        setWorkbenchData(segmentData);

        const suggestRes = await fetch(`http://127.0.0.1:8000/segments/${segmentId}/topics:suggest`, { method: 'POST' });
        if (!suggestRes.ok) throw new Error('Failed to fetch topic suggestions.');
        const suggestData = await suggestRes.json();
        
        setInitialTopics(suggestData.suggestions);
        const initialStagedChanges = suggestData.suggestions.reduce((acc: Record<string, StagedChange>, topic: TopicSuggestion) => {
          const key = topic.topic_id || `new-${topic.name}`;
          acc[key] = { ...topic, isDirty: false, markedForSave: false };
          return acc;
        }, {});
        setStagedChanges(initialStagedChanges);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'An unknown error occurred');
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, [segmentId]);

  // --- Event Handlers ---
  const handleTopicSelect = (topic: TopicSuggestion) => {
    const key = topic.topic_id || `new-${topic.name}`;
    setActiveTopicKey(key);
  };

  const handleStagedChange = (field: keyof StagedChange, value: string | null) => {
    if (!activeTopicKey) return;
    setStagedChanges(prev => ({
      ...prev,
      [activeTopicKey]: { 
        ...prev[activeTopicKey], 
        [field]: value,
        // Mark as dirty when user edits content fields
        isDirty: ['name', 'description', 'user_hypothesis', 'summary_text'].includes(field) 
          ? true 
          : prev[activeTopicKey]?.isDirty,
      },
    }));
  };

  const toggleMarkedForSave = (key: string) => {
    setStagedChanges(prev => ({
      ...prev,
      [key]: { 
        ...prev[key], 
        markedForSave: !prev[key]?.markedForSave 
      },
    }));
  };

  const handleGeneratePov = async () => {
    if (!activeEditingTopic) return;
    setIsGeneratingPov(true);
    try {
      const response = await fetch('http://127.0.0.1:8000/analysis:generate_pov', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          segment_id: segmentId,
          topic_name: activeEditingTopic.name,
          description: activeEditingTopic.description,
          user_hypothesis: activeEditingTopic.user_hypothesis,
        }),
      });
      if (!response.ok) throw new Error('Failed to generate Analyst POV.');
      const data = await response.json();

      if (activeTopicKey) {
        setStagedChanges(prev => ({
          ...prev,
          [activeTopicKey]: { 
            ...prev[activeTopicKey], 
            pov_summary: data.pov_summary,
            pov_id: data.pov_id,
            isDirty: true,
          },
        }));
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : 'An unknown error occurred');
    } finally {
      setIsGeneratingPov(false);
    }
  };

  const handleCheckHypothesis = async () => {
    if (!activeEditingTopic) return;
    setIsCheckingHypothesis(true);
    try {
      const response = await fetch('http://127.0.0.1:8000/analysis:check_hypothesis', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          segment_text: workbenchData?.segment.text || "",
          topic_name: activeEditingTopic.name,
          user_hypothesis: activeEditingTopic.user_hypothesis,
        }),
      });
      if (!response.ok) throw new Error('Failed to run hypothesis analysis.');
      const data = await response.json();

      if (activeTopicKey) {
        setStagedChanges(prev => ({
          ...prev,
          [activeTopicKey]: { 
            ...prev[activeTopicKey], 
            summary_text: data.analysis_text,
            isDirty: true,
          },
        }));
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : 'An unknown error occurred');
    } finally {
      setIsCheckingHypothesis(false);
    }
  };

  const handleFinalSave = async () => {
    // Only save topics that are marked for save
    const topicsToSave = Object.values(stagedChanges).filter(t => t.markedForSave);
    
    if (topicsToSave.length === 0) {
      alert('No topics selected for saving. Check the boxes next to topics you want to save.');
      return;
    }

    setIsSaving(true);
    setSaveSuccess(false);
    
    try {
      const response = await fetch(`http://127.0.0.1:8000/segments/${segmentId}/topics`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          topics: topicsToSave.map(t => ({
            topic_id: t.topic_id || null,  // Ensure null for new topics
            name: t.name,
            description: t.description || null,
            user_hypothesis: t.user_hypothesis || null,
            summary_text: t.summary_text || null,
            pov_id: t.pov_id || null,
          }))
        }),
      });
      
      if (!response.ok) {
        // Try to get error details from response
        let errorMessage = 'Failed to save changes.';
        try {
          const errorData = await response.json();
          errorMessage = errorData.detail || errorMessage;
        } catch {
          // Response might not be JSON (e.g., 500 error)
          errorMessage = `Server error: ${response.status} ${response.statusText}`;
        }
        throw new Error(errorMessage);
      }
      
      // Success! (204 No Content)
      setSaveSuccess(true);
      
      // Clear the saved topics from the list after successful save
      setStagedChanges(prev => {
        const updated = { ...prev };
        Object.keys(updated).forEach(key => {
          if (updated[key].markedForSave) {
            updated[key] = { ...updated[key], markedForSave: false, isDirty: false };
          }
        });
        return updated;
      });
      
      // Show success message briefly, then redirect to segments list
      setTimeout(() => {
        router.push('/');
      }, 1500);
      
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      alert(`Save failed: ${message}`);
      console.error('Save error:', err);
    } finally {
      setIsSaving(false);
    }
  };

  // --- UI Rendering ---
  if (isLoading) return <div className="p-12 text-center">Loading workbench...</div>;
  if (error) return <div className="p-12 text-center text-red-500">Error: {error}</div>;

  return (
    <main className="flex min-h-screen flex-col p-8 lg:p-12 bg-gray-50 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <h1 className="text-2xl lg:text-3xl font-bold text-gray-800">Segment & Topic Analyzer</h1>
        <div className="flex items-center gap-4">
          {saveSuccess && (
            <span className="text-green-600 font-medium">✓ Saved successfully!</span>
          )}
          <button
            onClick={handleFinalSave}
            disabled={isSaving || topicsToSaveCount === 0}
            className="px-6 py-2 font-semibold text-white bg-green-600 rounded-md hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
          >
            {isSaving ? 'Saving...' : `Save ${topicsToSaveCount > 0 ? `(${topicsToSaveCount})` : 'Selected'}`}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 lg:gap-8">
        {/* --- Left Column: Topic Selection & Editing --- */}
        <div className="space-y-6">
          {/* --- Section 1: Suggested Topics Table --- */}
          <section>
            <h2 className="text-lg font-semibold text-gray-700 mb-3">1. Select a Topic to Analyze</h2>
            <div className="bg-white rounded-lg shadow overflow-hidden">
              <table className="min-w-full text-sm divide-y divide-gray-200">
                <thead className="bg-gray-100">
                  <tr>
                    <th className="px-3 py-3 text-left font-semibold text-gray-600 w-10">Save</th>
                    <th className="px-3 py-3 text-left font-semibold text-gray-600">Topic Name</th>
                    <th className="px-3 py-3 text-left font-semibold text-gray-600 w-24">Source</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {initialTopics.map((topic) => {
                    const key = topic.topic_id || `new-${topic.name}`;
                    const staged = stagedChanges[key];
                    const isActive = activeTopicKey === key;
                    const isDirty = staged?.isDirty;
                    const isMarked = staged?.markedForSave;
                    
                    return (
                      <tr 
                        key={key} 
                        className={`cursor-pointer transition-colors ${
                          isActive 
                            ? 'bg-blue-100' 
                            : isDirty 
                              ? 'bg-yellow-50 hover:bg-yellow-100' 
                              : 'hover:bg-gray-50'
                        }`}
                      >
                        <td className="px-3 py-3" onClick={(e) => e.stopPropagation()}>
                          <input
                            type="checkbox"
                            checked={isMarked || false}
                            onChange={() => toggleMarkedForSave(key)}
                            className="w-4 h-4 text-green-600 rounded border-gray-300 focus:ring-green-500"
                          />
                        </td>
                        <td 
                          className="px-3 py-3 font-medium text-gray-800"
                          onClick={() => handleTopicSelect(topic)}
                        >
                          <span className="flex items-center gap-2">
                            {staged?.name || topic.name}
                            {isDirty && <span className="text-xs text-yellow-600">●</span>}
                          </span>
                        </td>
                        <td 
                          className="px-3 py-3 text-gray-600"
                          onClick={() => handleTopicSelect(topic)}
                        >
                          {topic.source}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <p className="mt-2 text-xs text-gray-500">
              Check the box next to topics you want to save. Yellow dot (●) indicates unsaved changes.
            </p>
          </section>

          {/* --- Section 2: Topic Analysis & Editing Form --- */}
          <section>
            <h2 className="text-lg font-semibold text-gray-700 mb-3">2. Assess Topic</h2>
            {activeEditingTopic ? (
              <div className="p-5 bg-white rounded-lg shadow space-y-5">
                {/* Topic Name */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Topic Name</label>
                  <input
                    type="text"
                    value={activeEditingTopic.name || ''}
                    onChange={e => handleStagedChange('name', e.target.value)}
                    className="block w-full px-3 py-2 bg-white border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 text-sm text-gray-900"
                  />
                </div>
                
                {/* Description Field */}
                <div>
                  <div className="flex justify-between items-center mb-1">
                    <label className="block text-sm font-medium text-gray-700">Description (Markdown)</label>
                    <button 
                      onClick={() => handleStagedChange('editingField', activeEditingTopic.editingField === 'description' ? null : 'description')}
                      className="text-xs text-blue-600 hover:underline"
                    >
                      {activeEditingTopic.editingField === 'description' ? 'Preview' : 'Edit'}
                    </button>
                  </div>
                  {activeEditingTopic.editingField === 'description' ? (
                    <textarea
                      value={activeEditingTopic.description || ''}
                      onChange={e => handleStagedChange('description', e.target.value)}
                      rows={4}
                      className="block w-full px-3 py-2 bg-white border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 text-sm text-gray-900 font-mono"
                      placeholder="Enter markdown description..."
                    />
                  ) : (
                    <div 
                      className="block w-full px-3 py-2 bg-gray-50 border border-gray-300 rounded-md min-h-[100px] prose prose-sm max-w-none text-gray-900 cursor-pointer hover:bg-gray-100"
                      onClick={() => handleStagedChange('editingField', 'description')}
                    >
                      <ReactMarkdown>{activeEditingTopic.description || '*No description.*'}</ReactMarkdown>
                    </div>
                  )}
                </div>

                {/* User Hypothesis Field */}
                <div>
                  <div className="flex justify-between items-center mb-1">
                    <label className="block text-sm font-medium text-gray-700">User Hypothesis (Markdown)</label>
                    <button 
                      onClick={() => handleStagedChange('editingField', activeEditingTopic.editingField === 'user_hypothesis' ? null : 'user_hypothesis')}
                      className="text-xs text-blue-600 hover:underline"
                    >
                      {activeEditingTopic.editingField === 'user_hypothesis' ? 'Preview' : 'Edit'}
                    </button>
                  </div>
                  {activeEditingTopic.editingField === 'user_hypothesis' ? (
                    <textarea
                      value={activeEditingTopic.user_hypothesis || ''}
                      onChange={e => handleStagedChange('user_hypothesis', e.target.value)}
                      rows={4}
                      className="block w-full px-3 py-2 bg-white border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 text-sm text-gray-900 font-mono"
                      placeholder="Enter markdown hypothesis..."
                    />
                  ) : (
                    <div 
                      className="block w-full px-3 py-2 bg-gray-50 border border-gray-300 rounded-md min-h-[100px] prose prose-sm max-w-none text-gray-900 cursor-pointer hover:bg-gray-100"
                      onClick={() => handleStagedChange('editingField', 'user_hypothesis')}
                    >
                      <ReactMarkdown>{activeEditingTopic.user_hypothesis || '*No hypothesis.*'}</ReactMarkdown>
                    </div>
                  )}
                </div>

                {/* Segment <> Topic Analysis */}
                <div className="pt-4 border-t border-gray-200">
                  <div className="flex justify-between items-center mb-2">
                    <label className="block text-sm font-medium text-gray-700">Segment &lt;&gt; Topic Analysis</label>
                    <button
                      onClick={handleCheckHypothesis}
                      disabled={isCheckingHypothesis || !activeEditingTopic.user_hypothesis}
                      className="px-3 py-1.5 text-xs font-medium text-white bg-indigo-600 rounded hover:bg-indigo-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
                    >
                      {isCheckingHypothesis ? 'Analyzing...' : 'Run Hypothesis Analysis'}
                    </button>
                  </div>
                  <textarea
                    value={activeEditingTopic.summary_text || ''}
                    onChange={e => handleStagedChange('summary_text', e.target.value)}
                    rows={4}
                    placeholder="Does this segment confirm, refute, or nuance the hypothesis?"
                    className="block w-full px-3 py-2 bg-white border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 text-sm text-gray-900"
                  />
                </div>

                {/* Analyst POV */}
                <div className="p-4 bg-gray-50 rounded-md border border-gray-200">
                  <div className="flex justify-between items-center">
                    <h3 className="font-semibold text-gray-800 text-sm">Analyst POV</h3>
                    <button
                      onClick={handleGeneratePov}
                      disabled={isGeneratingPov}
                      className="px-3 py-1.5 font-medium text-xs text-white bg-blue-600 rounded hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
                    >
                      {isGeneratingPov ? 'Generating...' : 'Get Analyst POV'}
                    </button>
                  </div>
                  <p className="mt-2 text-sm text-gray-700 whitespace-pre-wrap">
                    {activeEditingTopic.pov_summary || <span className="text-gray-500 italic">Click button to generate Analyst POV.</span>}
                  </p>
                </div>

                {/* Mark for Save button */}
                <div className="pt-4 border-t border-gray-200">
                  <button
                    onClick={() => activeTopicKey && toggleMarkedForSave(activeTopicKey)}
                    className={`w-full py-2 font-medium rounded-md transition-colors ${
                      activeEditingTopic.markedForSave
                        ? 'bg-green-100 text-green-800 border border-green-300 hover:bg-green-200'
                        : 'bg-gray-100 text-gray-700 border border-gray-300 hover:bg-gray-200'
                    }`}
                  >
                    {activeEditingTopic.markedForSave ? '✓ Marked for Save' : 'Mark for Save'}
                  </button>
                </div>
              </div>
            ) : (
              <div className="p-6 bg-white rounded-lg shadow text-center text-gray-500">
                Select a topic from the table above to edit its details.
              </div>
            )}
          </section>
        </div>

        {/* --- Right Column: Segment Content --- */}
        <section>
          <h2 className="text-lg font-semibold text-gray-700 mb-3">
            Segment Content
          </h2>
          <div
            className="prose prose-sm max-w-none p-5 bg-white rounded-lg shadow max-h-[calc(100vh-180px)] overflow-y-auto whitespace-pre-wrap text-gray-900"
            dangerouslySetInnerHTML={{ __html: workbenchData?.segment.content_html || workbenchData?.segment.text || '' }}
          />
        </section>
      </div>
    </main>
  );
}
