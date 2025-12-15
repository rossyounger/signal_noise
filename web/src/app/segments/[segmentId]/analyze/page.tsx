"use client";

import { useEffect, useState, useMemo } from 'react';
import { useParams, useRouter } from 'next/navigation';
import ReactMarkdown from 'react-markdown';

// --- Type Definitions ---
type SegmentWorkbenchContent = {
  segment: { id: string; document_id: string; text: string; content_html: string | null; };
  document: { id: string; url: string; title: string; author: string | null; html_content: string | null; };
};

type HypothesisSuggestion = {
  hypothesis_id?: string;
  hypothesis_text: string;
  source: 'existing' | 'generated' | 'Linked';
  description?: string;
  analysis_text?: string;
  _key?: string; // Internal key for deduplication (not sent to API)
};

type AvailableHypothesis = {
  hypothesis_id: string;
  hypothesis_text: string | null;
  description: string | null;
  reference_url: string | null;
  reference_type: string | null;
};

type SegmentHypothesis = {
  hypothesis_id: string;
  hypothesis_text: string | null;
  description: string | null;
  reference_url: string | null;
  reference_type: string | null;
  verdict: string | null;
  analysis_text: string | null;
  created_at: string;
};

// Represents a hypothesis being edited, including its AI-generated POV
type StagedChange = HypothesisSuggestion & {
  verdict?: string;
  pov_summary?: string;
  pov_id?: string;
  editingField?: 'description' | 'hypothesis_text' | null;
  isDirty?: boolean; // Track if user has modified this hypothesis
  markedForSave?: boolean; // Explicitly marked for saving
  reference_url?: string | null;
  reference_type?: string | null;
  includeFullReference?: boolean; // User toggle for deep analysis
  analysisMode?: 'summary' | 'full_reference'; // Track which mode was used
};

// --- Page Component ---
export default function SegmentAnalyzePage() {
  const params = useParams();
  const router = useRouter();
  const segmentId = params.segmentId as string;

  // --- State Management ---
  const [workbenchData, setWorkbenchData] = useState<SegmentWorkbenchContent | null>(null);
  const [existingHypotheses, setExistingHypotheses] = useState<SegmentHypothesis[]>([]);
  const [aiSuggestions, setAiSuggestions] = useState<HypothesisSuggestion[]>([]);
  const [linkedHypotheses, setLinkedHypotheses] = useState<HypothesisSuggestion[]>([]);
  const [stagedChanges, setStagedChanges] = useState<Record<string, StagedChange>>({});
  const [activeHypothesisKey, setActiveHypothesisKey] = useState<string | null>(null);

  // Modal State
  const [isHypothesisModalOpen, setHypothesisModalOpen] = useState(false);
  const [availableHypotheses, setAvailableHypotheses] = useState<AvailableHypothesis[]>([]);

  const [isLoading, setIsLoading] = useState(true);
  const [isGeneratingSuggestions, setIsGeneratingSuggestions] = useState(false);
  const [isGeneratingPov, setIsGeneratingPov] = useState(false);
  const [isCheckingHypothesis, setIsCheckingHypothesis] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Memoized derived state
  const activeEditingHypothesis = useMemo(() => {
    if (!activeHypothesisKey) return null;
    return stagedChanges[activeHypothesisKey];
  }, [activeHypothesisKey, stagedChanges]);

  // Combine all hypotheses into a single list
  const allHypotheses = useMemo(() => {
    const hypothesisMap = new Map<string, HypothesisSuggestion>();

    // 1. Existing Hypotheses (from DB for this segment)
    existingHypotheses.forEach(h => {
      hypothesisMap.set(h.hypothesis_id, {
        hypothesis_id: h.hypothesis_id,
        hypothesis_text: h.hypothesis_text || '',
        source: 'existing',
        description: h.description || undefined,
        analysis_text: h.analysis_text || undefined,
        _key: h.hypothesis_id,
      });
    });

    // 2. Linked Hypotheses (manually selected this session)
    linkedHypotheses.forEach(h => {
      if (!hypothesisMap.has(h.hypothesis_id!)) {
        hypothesisMap.set(h.hypothesis_id!, h);
      }
    });

    // 3. AI Suggestions
    let newHypothesisCounter = 0;
    aiSuggestions.forEach(h => {
      const key = h.hypothesis_id || `new-${newHypothesisCounter++}-${h.hypothesis_text.slice(0, 20)}`;
      if (!h.hypothesis_id) {
        if (!hypothesisMap.has(key)) hypothesisMap.set(key, { ...h, _key: key });
      } else {
        if (!hypothesisMap.has(h.hypothesis_id)) hypothesisMap.set(h.hypothesis_id, { ...h, _key: h.hypothesis_id });
      }
    });

    return Array.from(hypothesisMap.values());
  }, [existingHypotheses, aiSuggestions, linkedHypotheses]);

  // Count hypotheses marked for save
  const hypothesesToSaveCount = useMemo(() => {
    return Object.values(stagedChanges).filter(h => h.markedForSave).length;
  }, [stagedChanges]);

  // --- Data Fetching ---
  useEffect(() => {
    if (!segmentId) return;
    const fetchData = async () => {
      try {
        // Fetch segment data
        const segmentRes = await fetch(`http://127.0.0.1:8000/segments/${segmentId}`);
        if (!segmentRes.ok) throw new Error('Failed to fetch segment details.');
        const segmentData: SegmentWorkbenchContent = await segmentRes.json();
        setWorkbenchData(segmentData);

        // Fetch existing hypotheses linked to this segment
        const existingRes = await fetch(`http://127.0.0.1:8000/segments/${segmentId}/hypotheses`);
        if (!existingRes.ok) throw new Error('Failed to fetch existing hypotheses.');
        const existingData: SegmentHypothesis[] = await existingRes.json();
        setExistingHypotheses(existingData);

        // Initialize staged changes for existing hypotheses
        const initialStagedChanges = existingData.reduce((acc: Record<string, StagedChange>, hyp: SegmentHypothesis) => {
          const key = hyp.hypothesis_id;
          acc[key] = {
            hypothesis_id: hyp.hypothesis_id,
            hypothesis_text: hyp.hypothesis_text || '',
            source: 'existing',
            description: hyp.description || undefined,
            analysis_text: hyp.analysis_text || undefined,
            verdict: hyp.verdict || undefined,
            isDirty: false,
            markedForSave: false,
          };
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

  // Handler for generating AI suggestions
  const handleGenerateSuggestions = async () => {
    if (!segmentId) return;
    setIsGeneratingSuggestions(true);
    try {
      const suggestRes = await fetch(`http://127.0.0.1:8000/segments/${segmentId}/hypotheses:suggest`, { method: 'POST' });
      if (!suggestRes.ok) throw new Error('Failed to fetch hypothesis suggestions.');
      const suggestData = await suggestRes.json();

      setAiSuggestions(suggestData.suggestions);

      // Add AI suggestions to staged changes with unique keys
      setStagedChanges(prev => {
        const updated = { ...prev };
        let newHypothesisCounter = 0;
        suggestData.suggestions.forEach((hyp: HypothesisSuggestion) => {
          const key = hyp.hypothesis_id || `new-${newHypothesisCounter++}-${hyp.hypothesis_text.slice(0, 20)}`;
          if (!updated[key]) {
            updated[key] = { ...hyp, _key: key, isDirty: false, markedForSave: false };
          }
        });
        return updated;
      });
    } catch (err) {
      alert(err instanceof Error ? err.message : 'An unknown error occurred');
    } finally {
      setIsGeneratingSuggestions(false);
    }
  };

  // --- Event Handlers ---
  const handleCheckboxChange = (key: string, checked: boolean) => {
    if (checked) {
      // Only one checkbox can be checked at a time - uncheck others first
      if (activeHypothesisKey && activeHypothesisKey !== key) {
        setStagedChanges(prev => ({
          ...prev,
          [activeHypothesisKey]: {
            ...prev[activeHypothesisKey],
            markedForSave: false
          },
        }));
      }
      // Set new active hypothesis
      setActiveHypothesisKey(key);
      // Mark for save when checking
      setStagedChanges(prev => ({
        ...prev,
        [key]: {
          ...prev[key],
          markedForSave: true
        },
      }));
    } else {
      // Unchecking clears selection and hides edit form
      setActiveHypothesisKey(null);
      // Unmark for save when unchecking
      setStagedChanges(prev => ({
        ...prev,
        [key]: {
          ...prev[key],
          markedForSave: false
        },
      }));
    }
  };

  const handleStagedChange = (field: keyof StagedChange, value: string | boolean | null) => {
    if (!activeHypothesisKey) return;
    setStagedChanges(prev => ({
      ...prev,
      [activeHypothesisKey]: {
        ...prev[activeHypothesisKey],
        [field]: value,
        // Mark as dirty when user edits content fields
        isDirty: ['hypothesis_text', 'description', 'analysis_text', 'includeFullReference'].includes(field)
          ? true
          : prev[activeHypothesisKey]?.isDirty,
      },
    }));
  };

  // Refresh existing hypotheses after save
  const refreshExistingHypotheses = async () => {
    if (!segmentId) return;
    try {
      const existingRes = await fetch(`http://127.0.0.1:8000/segments/${segmentId}/hypotheses`);
      if (existingRes.ok) {
        const existingData: SegmentHypothesis[] = await existingRes.json();
        setExistingHypotheses(existingData);

        // Update staged changes with refreshed data
        setStagedChanges(prev => {
          const updated = { ...prev };
          existingData.forEach((hyp: SegmentHypothesis) => {
            const key = hyp.hypothesis_id;
            if (updated[key]) {
              updated[key] = {
                ...updated[key],
                hypothesis_text: hyp.hypothesis_text || '',
                description: hyp.description || undefined,
                analysis_text: hyp.analysis_text || undefined,
                verdict: hyp.verdict || undefined,
              };
            }
          });
          return updated;
        });
      }
    } catch (err) {
      console.error('Failed to refresh existing hypotheses:', err);
    }
  };

  const handleGeneratePov = async () => {
    if (!activeEditingHypothesis) return;
    setIsGeneratingPov(true);
    try {
      const response = await fetch('http://127.0.0.1:8000/analysis:generate_pov', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          segment_id: segmentId,
          hypothesis_text: activeEditingHypothesis.hypothesis_text,
          description: activeEditingHypothesis.description,
        }),
      });
      if (!response.ok) throw new Error('Failed to generate Analyst POV.');
      const data = await response.json();

      if (activeHypothesisKey) {
        setStagedChanges(prev => ({
          ...prev,
          [activeHypothesisKey]: {
            ...prev[activeHypothesisKey],
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
    if (!activeEditingHypothesis) return;
    setIsCheckingHypothesis(true);
    try {
      const response = await fetch('http://127.0.0.1:8000/analysis:check_hypothesis', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          segment_text: workbenchData?.segment.text || "",
          hypothesis_text: activeEditingHypothesis.hypothesis_text,
          hypothesis_description: activeEditingHypothesis.description,
          reference_url: activeEditingHypothesis.reference_url,
          include_full_reference: activeEditingHypothesis.includeFullReference || false,
          hypothesis_id: activeEditingHypothesis.hypothesis_id || null,
        }),
      });
      if (!response.ok) throw new Error('Failed to run hypothesis analysis.');
      const data = await response.json();

      if (activeHypothesisKey) {
        setStagedChanges(prev => ({
          ...prev,
          [activeHypothesisKey]: {
            ...prev[activeHypothesisKey],
            analysis_text: data.analysis_text,
            analysisMode: activeEditingHypothesis.includeFullReference ? 'full_reference' : 'summary',
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
    // Only save hypotheses that are marked for save
    const hypothesesToSave = Object.values(stagedChanges).filter(h => h.markedForSave);

    if (hypothesesToSave.length === 0) {
      alert('No hypotheses selected for saving. Check the boxes next to hypotheses you want to save.');
      return;
    }

    setIsSaving(true);
    setSaveSuccess(false);

    try {
      const response = await fetch(`http://127.0.0.1:8000/segments/${segmentId}/evidence`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          evidence: hypothesesToSave.map(h => ({
            hypothesis_id: (h.hypothesis_id && h.hypothesis_id.trim()) || null,
            hypothesis_text: h.hypothesis_text,
            description: h.description || null,
            verdict: h.verdict || null,
            analysis_text: h.analysis_text || null,
            pov_id: h.pov_id || null,
          }))
        }),
      });

      if (!response.ok) {
        let errorMessage = 'Failed to save changes.';
        try {
          const errorData = await response.json();
          errorMessage = errorData.detail || errorMessage;
        } catch {
          errorMessage = `Server error: ${response.status} ${response.statusText}`;
        }
        throw new Error(errorMessage);
      }

      // Success! (204 No Content)
      setSaveSuccess(true);

      // Clear the saved hypotheses from the list after successful save
      setStagedChanges(prev => {
        const updated = { ...prev };
        Object.keys(updated).forEach(key => {
          if (updated[key].markedForSave) {
            updated[key] = { ...updated[key], markedForSave: false, isDirty: false };
          }
        });
        return updated;
      });

      // Clear selection (uncheck checkbox)
      setActiveHypothesisKey(null);

      // Refresh existing hypotheses to show updated data
      await refreshExistingHypotheses();

      // Clear linked hypotheses that have been saved
      setLinkedHypotheses(prev => prev.filter(h => !hypothesesToSave.find(saved => saved.hypothesis_id === h.hypothesis_id)));

      // Show success message briefly
      setTimeout(() => {
        setSaveSuccess(false);
      }, 2000);

    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      alert(`Save failed: ${message}`);
      console.error('Save error:', err);
    } finally {
      setIsSaving(false);
    }
  };

  const fetchAvailableHypotheses = async () => {
    try {
      const response = await fetch('http://127.0.0.1:8000/hypotheses');
      if (!response.ok) throw new Error('Failed to fetch available hypotheses.');
      const data = await response.json();
      // Map the API response to our expected format
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

  const handleSelectHypothesis = (hyp: AvailableHypothesis) => {
    // Check if this hypothesis is already linked
    const isAlreadyPresent = existingHypotheses.some(h => h.hypothesis_id === hyp.hypothesis_id) ||
      linkedHypotheses.some(h => h.hypothesis_id === hyp.hypothesis_id);

    if (isAlreadyPresent) {
      alert('This hypothesis is already associated with this segment.');
      setHypothesisModalOpen(false);
      return;
    }

    const newLinkedHypothesis: StagedChange = {
      hypothesis_id: hyp.hypothesis_id,
      hypothesis_text: hyp.hypothesis_text || 'Untitled Hypothesis',
      description: hyp.description || undefined,
      reference_url: hyp.reference_url || undefined,
      reference_type: hyp.reference_type || undefined,
      analysis_text: undefined,
      pov_id: undefined,
      pov_summary: undefined,
      markedForSave: true,
      isDirty: true,
      _key: hyp.hypothesis_id,
      source: 'Linked',
    };

    setLinkedHypotheses(prev => [...prev, newLinkedHypothesis]);

    // Add to stagedChanges so the edit form has data to display
    setStagedChanges(prev => ({
      ...prev,
      [hyp.hypothesis_id]: newLinkedHypothesis
    }));

    setHypothesisModalOpen(false);
    setActiveHypothesisKey(hyp.hypothesis_id);
  };


  // --- Section State ---
  const [sections, setSections] = useState({
    selectHypotheses: true,
    assessHypothesis: true,
    segmentContent: true
  });

  const toggleSection = (key: keyof typeof sections) => {
    setSections(prev => ({ ...prev, [key]: !prev[key] }));
  };

  // --- UI Rendering ---
  if (isLoading) return <div className="p-12 text-center">Loading workbench...</div>;
  if (error) return <div className="p-12 text-center text-red-500">Error: {error}</div>;

  return (
    <main className="flex min-h-screen flex-col p-8 lg:p-12 bg-gray-50 space-y-6 relative">
      {/* Header */}
      <div className="flex justify-between items-center">
        <h1 className="text-2xl lg:text-3xl font-bold text-gray-800">Segment & Hypothesis Analyzer</h1>
      </div>

      <div className="space-y-6 max-w-5xl mx-auto w-full">

        {/* --- Section 1: Select Hypotheses --- */}
        <div className="bg-white rounded-lg shadow overflow-hidden border border-gray-200">
          <div
            className="px-4 py-3 bg-gray-100 border-b border-gray-200 flex justify-between items-center cursor-pointer select-none"
            onClick={() => toggleSection('selectHypotheses')}
          >
            <h2 className="text-lg font-semibold text-gray-700 flex items-center gap-2">
              <span className={`transform transition-transform ${sections.selectHypotheses ? 'rotate-90' : ''}`}>▶</span>
              1. Select Hypotheses
            </h2>
          </div>

          {sections.selectHypotheses && (
            <div className="p-4 space-y-4">
              {/* Toolbar Row */}
              <div className="flex gap-4 items-center">
                <button
                  onClick={handleGenerateSuggestions}
                  disabled={isGeneratingSuggestions || activeHypothesisKey !== null}
                  className="flex-1 py-2 text-sm font-medium text-white bg-indigo-600 rounded shadow-sm hover:bg-indigo-700 disabled:bg-indigo-400 disabled:cursor-not-allowed transition-colors"
                >
                  {isGeneratingSuggestions ? 'Generating Suggestions...' : 'Generate AI Hypothesis Suggestions'}
                </button>
                <button
                  onClick={handleLinkExisting}
                  className="px-6 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded shadow-sm hover:bg-gray-50 transition-colors"
                >
                  Link Existing Hypothesis
                </button>
              </div>

              {/* Hypotheses Table */}
              <div className="bg-white rounded border border-gray-200 overflow-hidden">
                <table className="min-w-full text-sm divide-y divide-gray-200">
                  <thead className="bg-gray-50 text-xs uppercase font-medium text-gray-500">
                    <tr>
                      <th className="px-4 py-3 text-left w-12">Save</th>
                      <th className="px-4 py-3 text-left">Hypothesis</th>
                      <th className="px-4 py-3 text-left w-32">Source</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {allHypotheses.length === 0 ? (
                      <tr>
                        <td colSpan={3} className="px-4 py-8 text-center text-gray-500 italic">
                          No hypotheses yet. Generate suggestions or link an existing one to start.
                        </td>
                      </tr>
                    ) : (
                      allHypotheses.map((hyp) => {
                        const key = hyp._key || hyp.hypothesis_id || `new-${hyp.hypothesis_text.slice(0, 20)}`;
                        const staged = stagedChanges[key];
                        const isActive = activeHypothesisKey === key;
                        const isDirty = staged?.isDirty;

                        return (
                          <tr
                            key={key}
                            className={`cursor-pointer transition-colors ${isActive
                              ? 'bg-blue-50'
                              : isDirty
                                ? 'bg-yellow-50 hover:bg-yellow-100'
                                : 'hover:bg-gray-50'
                              }`}
                          >
                            <td className="px-4 py-3">
                              <input
                                type="checkbox"
                                checked={staged?.markedForSave || false}
                                onChange={(e) => handleCheckboxChange(key, e.target.checked)}
                                className="w-4 h-4 text-green-600 rounded border-gray-300 focus:ring-green-500 cursor-pointer"
                              />
                            </td>
                            <td className="px-4 py-3 font-medium text-gray-800">
                              {(staged?.hypothesis_text || hyp.hypothesis_text).slice(0, 100)}
                              {(staged?.hypothesis_text || hyp.hypothesis_text).length > 100 && '...'}
                              {isDirty && <span className="ml-2 text-xs text-yellow-600 font-normal">● Unsaved</span>}
                            </td>
                            <td className="px-4 py-3 text-gray-500">
                              {hyp.source}
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
              <p className="text-xs text-gray-500">
                Tip: Check the box to select a hypothesis for analysis and editing.
              </p>
            </div>
          )}
        </div>

        {/* --- Section 2: Assess Hypothesis --- */}
        <div className="bg-white rounded-lg shadow overflow-hidden border border-gray-200">
          <div className="px-4 py-3 bg-gray-100 border-b border-gray-200 flex justify-between items-center">
            <div
              className="flex items-center gap-2 cursor-pointer select-none"
              onClick={() => toggleSection('assessHypothesis')}
            >
              <h2 className="text-lg font-semibold text-gray-900">
                <span className={`inline-block transform transition-transform ${sections.assessHypothesis ? 'rotate-90' : ''}`}>▶</span>
                2. Assess Hypothesis
              </h2>
            </div>

            {/* Header Action: Save Button */}
            {hypothesesToSaveCount > 0 && (
              <div className="flex items-center gap-3">
                {saveSuccess && (
                  <span className="text-green-600 font-medium text-sm animate-pulse">✓ Saved!</span>
                )}
                <button
                  onClick={handleFinalSave}
                  disabled={isSaving}
                  className="px-4 py-1.5 text-sm font-semibold text-white bg-green-600 rounded hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors shadow-sm"
                >
                  {isSaving ? 'Saving...' : `Save Evidence (${hypothesesToSaveCount})`}
                </button>
              </div>
            )}
          </div>

          {sections.assessHypothesis && (
            <div className="p-6">
              {activeEditingHypothesis ? (
                <div className="space-y-6">
                  {/* Hypothesis Text */}
                  <div>
                    <div className="flex justify-between items-center mb-1">
                      <label className="block text-sm font-medium text-gray-900">Hypothesis</label>
                      <button
                        onClick={() => handleStagedChange('editingField', activeEditingHypothesis.editingField === 'hypothesis_text' ? null : 'hypothesis_text')}
                        className="text-xs font-medium text-blue-600 hover:text-blue-800"
                      >
                        {activeEditingHypothesis.editingField === 'hypothesis_text' ? 'Done' : 'Edit'}
                      </button>
                    </div>
                    {activeEditingHypothesis.editingField === 'hypothesis_text' ? (
                      <textarea
                        value={activeEditingHypothesis.hypothesis_text || ''}
                        onChange={e => handleStagedChange('hypothesis_text', e.target.value)}
                        rows={3}
                        className="block w-full px-4 py-3 bg-white border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm text-black"
                        placeholder="Enter your hypothesis..."
                      />
                    ) : (
                      <div
                        className="block w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-md min-h-[80px] prose prose-sm max-w-none hover:bg-gray-100 cursor-text transition-colors text-black"
                        onClick={() => handleStagedChange('editingField', 'hypothesis_text')}
                      >
                        <ReactMarkdown>{activeEditingHypothesis.hypothesis_text || '*No hypothesis text.*'}</ReactMarkdown>
                      </div>
                    )}
                  </div>

                  {/* Description Field */}
                  <div>
                    <div className="flex justify-between items-center mb-1">
                      <label className="block text-sm font-medium text-gray-900">Context / Description (Markdown)</label>
                      <button
                        onClick={() => handleStagedChange('editingField', activeEditingHypothesis.editingField === 'description' ? null : 'description')}
                        className="text-xs font-medium text-blue-600 hover:text-blue-800"
                      >
                        {activeEditingHypothesis.editingField === 'description' ? 'Done' : 'Edit'}
                      </button>
                    </div>
                    {activeEditingHypothesis.editingField === 'description' ? (
                      <textarea
                        value={activeEditingHypothesis.description || ''}
                        onChange={e => handleStagedChange('description', e.target.value)}
                        rows={5}
                        className="block w-full px-4 py-3 bg-white border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-mono text-sm text-black"
                        placeholder="Enter context or description..."
                      />
                    ) : (
                      <div
                        className="block w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-md min-h-[100px] prose prose-sm max-w-none hover:bg-gray-100 cursor-text transition-colors text-black"
                        onClick={() => handleStagedChange('editingField', 'description')}
                      >
                        <ReactMarkdown>{activeEditingHypothesis.description || '*No description.*'}</ReactMarkdown>
                      </div>
                    )}
                  </div>

                  {/* Segment <> Hypothesis Analysis */}
                  <div className="pt-6 border-t border-gray-200">
                    {/* Reference Indicator */}
                    {activeEditingHypothesis.reference_url && (
                      <div className="mb-4 p-3 bg-purple-50 border border-purple-200 rounded-lg">
                        <div className="flex items-center gap-2 text-sm">
                          <span className="font-medium text-purple-900">📄 Based on:</span>
                          <a 
                            href={activeEditingHypothesis.reference_url} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            className="text-purple-700 hover:text-purple-900 underline"
                          >
                            {activeEditingHypothesis.reference_type ? 
                              `${activeEditingHypothesis.reference_type.charAt(0).toUpperCase() + activeEditingHypothesis.reference_type.slice(1)} reference` 
                              : 'External reference'}
                          </a>
                        </div>
                      </div>
                    )}

                    <div className="flex justify-between items-center mb-3">
                      <label className="block text-sm font-medium text-gray-900">Evidence Analysis</label>
                      <div className="flex items-center gap-3">
                        {/* Full Reference Toggle */}
                        {activeEditingHypothesis.reference_url && (
                          <label className="flex items-center gap-2 text-xs text-gray-600 cursor-pointer group">
                            <input
                              type="checkbox"
                              checked={activeEditingHypothesis.includeFullReference || false}
                              onChange={(e) => handleStagedChange('includeFullReference', e.target.checked)}
                              className="w-4 h-4 text-purple-600 rounded border-gray-300 focus:ring-purple-500 cursor-pointer"
                            />
                            <span className="group-hover:text-gray-900" title="Include complete paper in analysis (uses more AI tokens, takes longer)">
                              Use full reference document
                            </span>
                          </label>
                        )}
                        <button
                          onClick={handleCheckHypothesis}
                          disabled={isCheckingHypothesis || !activeEditingHypothesis.hypothesis_text}
                          className="px-4 py-2 text-xs font-semibold text-white bg-indigo-600 rounded hover:bg-indigo-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
                        >
                          {isCheckingHypothesis ? 'Analyzing...' : 'Run Evidence Analysis'}
                        </button>
                      </div>
                    </div>

                    {/* Analysis Mode Badge */}
                    {activeEditingHypothesis.analysisMode && activeEditingHypothesis.analysis_text && (
                      <div className="mb-2">
                        <span className={`inline-block px-2 py-1 text-xs rounded ${
                          activeEditingHypothesis.analysisMode === 'full_reference' 
                            ? 'bg-purple-100 text-purple-800' 
                            : 'bg-gray-100 text-gray-800'
                        }`}>
                          Analyzed with: {activeEditingHypothesis.analysisMode === 'full_reference' ? 'Full reference' : 'Summary only'}
                        </span>
                      </div>
                    )}

                    <textarea
                      value={activeEditingHypothesis.analysis_text || ''}
                      onChange={e => handleStagedChange('analysis_text', e.target.value)}
                      rows={6}
                      placeholder="Does this segment confirm, refute, or nuance the hypothesis?"
                      className="block w-full px-4 py-3 bg-white border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm text-black"
                    />
                  </div>

                  {/* Analyst POV */}
                  <div className="p-5 bg-blue-50 rounded-lg border border-blue-100">
                    <div className="flex justify-between items-center mb-2">
                      <h3 className="font-semibold text-blue-900 text-sm">Analyst POV</h3>
                      <button
                        onClick={handleGeneratePov}
                        disabled={isGeneratingPov}
                        className="px-3 py-1.5 font-medium text-xs text-white bg-blue-600 rounded hover:bg-blue-700 disabled:bg-blue-300 disabled:cursor-not-allowed transition-colors"
                      >
                        {isGeneratingPov ? 'Generating...' : 'Get Analyst POV'}
                      </button>
                    </div>
                    <div className="prose prose-sm max-w-none text-blue-800">
                      <ReactMarkdown>{activeEditingHypothesis.pov_summary || '*Click button to generate Analyst POV.*'}</ReactMarkdown>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="py-12 bg-gray-50 rounded border border-dashed border-gray-300 text-center">
                  <p className="text-gray-500">Select a hypothesis from &quot;Select Hypotheses&quot; above to assess it here.</p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* --- Section 3: Segment Content --- */}
        <div className="bg-white rounded-lg shadow overflow-hidden border border-gray-200">
          <div
            className="px-4 py-3 bg-gray-100 border-b border-gray-200 flex justify-between items-center cursor-pointer select-none"
            onClick={() => toggleSection('segmentContent')}
          >
            <h2 className="text-lg font-semibold text-gray-700">
              <span className={`inline-block transform transition-transform ${sections.segmentContent ? 'rotate-90' : ''}`}>▶</span>
              3. Segment Content
            </h2>
          </div>

          {sections.segmentContent && (
            <div
              className="prose prose-sm max-w-none p-6 bg-white max-h-[calc(100vh-200px)] overflow-y-auto whitespace-pre-wrap text-gray-900 border-b border-gray-50"
              dangerouslySetInnerHTML={{ __html: workbenchData?.segment.content_html || workbenchData?.segment.text || '' }}
            />
          )}
        </div>
      </div>

      {/* --- Hypothesis Selection Modal --- */}
      {isHypothesisModalOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[80vh] flex flex-col">
            <div className="p-4 border-b flex justify-between items-center">
              <h3 className="text-lg font-bold text-gray-800">Link Existing Hypothesis</h3>
              <button onClick={() => setHypothesisModalOpen(false)} className="text-gray-500 hover:text-gray-700">✕</button>
            </div>

            <div className="p-4 flex-1 overflow-y-auto">
              <input
                type="text"
                placeholder="Search hypotheses..."
                className="w-full px-3 py-2 border rounded mb-4"
              />

              {availableHypotheses.length === 0 ? (
                <div className="text-center text-gray-500 py-8">Loading hypotheses...</div>
              ) : (
                <div className="divide-y">
                  {availableHypotheses.map(hyp => (
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
