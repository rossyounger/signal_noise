'use client';

import { useState, useEffect, useCallback } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';

interface HypothesisEvidenceEntry {
  evidence_id: string;
  hypothesis_id: string;
  segment_id: string;
  verdict: string | null;
  analysis_text: string | null;
  authored_by: string;
  created_at: string;
  hypothesis_updated_at: string;
  freshness_status: string;
  segment_text_preview: string | null;
  document_id: string | null;
  document_title: string | null;
}

function VerdictBadge({ verdict }: { verdict: string | null }) {
  if (!verdict) return <span className="text-gray-400">-</span>;
  
  const colors: Record<string, string> = {
    confirms: 'bg-green-100 text-green-800',
    refutes: 'bg-red-100 text-red-800',
    nuances: 'bg-yellow-100 text-yellow-800',
    irrelevant: 'bg-gray-100 text-gray-600',
  };
  
  const color = colors[verdict.toLowerCase()] || 'bg-gray-100 text-gray-600';
  
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${color}`}>
      {verdict.charAt(0).toUpperCase() + verdict.slice(1)}
    </span>
  );
}

function FreshnessBadge({ status }: { status: string }) {
  const normalized = (status || '').toLowerCase();
  if (normalized === 'stale') {
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-orange-100 text-orange-800">
        Stale
      </span>
    );
  }
  return (
    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
      Current
    </span>
  );
}

export default function HypothesisEvidencePage() {
  const params = useParams();
  const hypothesisId = params.hypothesisId as string;
  const [evidence, setEvidence] = useState<HypothesisEvidenceEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchEvidence = useCallback(async () => {
    try {
      if (!hypothesisId) return;
      const res = await fetch(`http://127.0.0.1:8000/hypotheses/${hypothesisId}/evidence`);
      if (!res.ok) throw new Error('Failed to fetch hypothesis evidence');
      const data = await res.json();
      setEvidence(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [hypothesisId]);

  useEffect(() => {
    fetchEvidence();
  }, [fetchEvidence]);

  if (loading) return <div className="p-8">Loading evidence...</div>;
  if (error) return <div className="p-8 text-red-600">Error: {error}</div>;

  return (
    <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
      <div className="px-4 py-6 sm:px-0">
        <div className="mb-6">
          <div className="flex items-center gap-4 mb-2">
            <Link
              href="/hypotheses"
              className="text-indigo-600 hover:text-indigo-800 text-sm"
            >
              ← Back to Hypotheses
            </Link>
          </div>
          <h1 className="text-2xl font-bold text-gray-900">Evidence Trail</h1>
          <p className="mt-1 text-sm text-gray-500">
            All segments linked to this hypothesis as evidence, sorted by date
          </p>
        </div>

        {/* Evidence Table */}
        <div className="bg-white shadow overflow-hidden sm:rounded-lg">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th scope="col" className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-24">
                    Status
                  </th>
                  <th scope="col" className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-28">
                    Verdict
                  </th>
                  <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Analysis
                  </th>
                  <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Segment
                  </th>
                  <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-28">
                    Evidence saved
                  </th>
                  <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-32">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {evidence.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-6 py-4 text-center text-sm text-gray-500">
                      No evidence found for this hypothesis. Analyze segments to add evidence.
                    </td>
                  </tr>
                ) : (
                  evidence.map((entry) => (
                    <tr key={entry.evidence_id} className="hover:bg-gray-50">
                      <td className="px-3 py-4">
                        <FreshnessBadge status={entry.freshness_status} />
                      </td>
                      <td className="px-3 py-4">
                        <VerdictBadge verdict={entry.verdict} />
                      </td>
                      <td className="px-4 py-4 text-sm text-gray-700 break-words whitespace-pre-line" style={{ minWidth: '350px', maxWidth: '450px' }}>
                        {entry.analysis_text || '-'}
                      </td>
                      <td className="px-4 py-4 text-sm text-gray-700 break-words" style={{ minWidth: '300px', maxWidth: '400px' }}>
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
