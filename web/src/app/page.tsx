"use client";

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';

// Define the structure of a Segment object from our API
type Segment = {
  id: string;
  document_id: string;
  title: string;
  author: string | null;
  text: string;
  created_at: string;
  published_at: string | null;
};

// This is the main component for our page
export default function SegmentsPage() {
  const router = useRouter(); // Get the router instance
  // State to hold the list of segments
  const [segments, setSegments] = useState<Segment[]>([]);
  // State to track which segment is currently selected
  const [selectedSegmentId, setSelectedSegmentId] = useState<string | null>(null);
  // State for loading and error messages
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // This effect runs once when the component mounts to fetch data
  useEffect(() => {
    // We define an async function inside the effect to fetch the data
    const fetchSegments = async () => {
      try {
        // NOTE: Make sure your FastAPI backend is running at this URL
        const response = await fetch('http://127.0.0.1:8000/segments');
        if (!response.ok) {
          throw new Error(`Failed to fetch segments: ${response.statusText}`);
        }
        const data: Segment[] = await response.json();
        setSegments(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'An unknown error occurred');
        // In case of error, you might want to clear segments
        setSegments([]); 
      } finally {
        setIsLoading(false);
      }
    };

    fetchSegments();
  }, []); // The empty array means this effect runs only once

  const handleAnalyzeClick = () => {
    if (selectedSegmentId) {
      // Navigate to the new analysis page
      router.push(`/segments/${selectedSegmentId}/analyze`);
    } else {
      alert('Please select a segment to analyze.');
    }
  };

  return (
    <main className="flex min-h-screen flex-col items-center p-12 bg-gray-50">
      <div className="w-full max-w-7xl">
        <h1 className="text-3xl font-bold text-gray-800 mb-6">Segments</h1>
        
        <div className="flex items-center mb-4">
          <button
            onClick={handleAnalyzeClick}
            disabled={!selectedSegmentId}
            className="px-4 py-2 font-semibold text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
            >
            Analyze Selected
          </button>
          {/* We can add the delete button later */}
        </div>

        <div className="overflow-x-auto bg-white rounded-lg shadow">
          <table className="min-w-full text-sm divide-y divide-gray-200">
            <thead className="bg-gray-100">
              <tr>
                <th className="px-4 py-3 w-12"></th>
                <th className="px-4 py-3 text-left font-semibold text-gray-600">Title</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-600">Author</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-600">Raw Text</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-600">Created At</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-600">Published At</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {isLoading && (
                <tr><td colSpan={7} className="p-4 text-center text-gray-500">Loading segments...</td></tr>
              )}
              {error && (
                <tr><td colSpan={7} className="p-4 text-center text-red-500">Error: {error}</td></tr>
              )}
              {!isLoading && !error && segments.map((segment) => (
                <tr
                  key={segment.id}
                  onClick={() => setSelectedSegmentId(segment.id)}
                  className={`cursor-pointer ${selectedSegmentId === segment.id ? 'bg-blue-50' : 'hover:bg-gray-50'}`}
                >
                  <td className="px-4 py-3 text-center">
                    <input
                      type="checkbox"
                      checked={selectedSegmentId === segment.id}
                      onChange={() => setSelectedSegmentId(segment.id)}
                      className="form-checkbox h-4 w-4 text-blue-600 rounded"
                    />
                  </td>
                  <td className="px-4 py-3 font-medium text-gray-800">{segment.title}</td>
                  <td className="px-4 py-3 text-gray-600">{segment.author || 'N/A'}</td>
                  <td className="px-4 py-3 text-gray-600 max-w-md truncate">{segment.text}</td>
                  <td className="px-4 py-3 text-gray-600">{new Date(segment.created_at).toLocaleString()}</td>
                  <td className="px-4 py-3 text-gray-600">{segment.published_at ? new Date(segment.published_at).toLocaleString() : 'N/A'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        </div>
      </main>
  );
}
