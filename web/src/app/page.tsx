"use client";

import { useState, useEffect } from 'react';
import Link from 'next/link';

// Define the structure of a Segment object from our API
type Segment = {
  id: string;
  document_id: string;
  title: string;
  author: string | null;
  text: string;
  created_at: string;
  published_at: string | null;
  topic_count: number;
};

// This is the main component for our page
export default function SegmentsPage() {
  // State to hold the list of segments
  const [segments, setSegments] = useState<Segment[]>([]);
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

  return (
    <main className="w-full px-4 py-6 lg:px-8">
      <div className="py-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">Segments</h1>
        <div className="bg-white shadow overflow-x-auto sm:rounded-lg">
          <table className="w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th scope="col" className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
                <th scope="col" className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-[25%]">
                  Document Title
                </th>
                <th scope="col" className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Author
                </th>
                <th scope="col" className="px-3 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                  # of linked topics
                </th>
                <th scope="col" className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Raw Text
                </th>
                <th scope="col" className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Created At
                </th>
                <th scope="col" className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Published At
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {isLoading && (
                <tr>
                  <td colSpan={7} className="px-6 py-4 text-center text-sm text-gray-500">
                    Loading segments...
                  </td>
                </tr>
              )}
              {error && (
                <tr>
                  <td colSpan={7} className="px-6 py-4 text-center text-sm text-red-500">
                    Error: {error}
                  </td>
                </tr>
              )}
              {!isLoading && !error && segments.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-6 py-4 text-center text-sm text-gray-500">
                    No segments found.
                  </td>
                </tr>
              )}
              {!isLoading && !error && segments.map((segment) => (
                <tr key={segment.id} className="hover:bg-gray-50 align-top">
                  <td className="px-3 py-3">
                    <div className="flex gap-2">
                      <Link
                        href={`/segments/${segment.id}/analyze`}
                        className="inline-flex items-center justify-center px-3 py-1.5 text-xs font-semibold text-white bg-indigo-600 rounded-md shadow-sm hover:bg-indigo-700 active:bg-indigo-800 transition-all"
                      >
                        Analyze
                      </Link>
                      <button
                        onClick={async () => {
                          if (confirm("this will delete the segment forever, are you sure?") && confirm("ARE YOU REALLY REALLY SURE??")) {
                            try {
                              const res = await fetch(`http://127.0.0.1:8000/segments/${segment.id}`, {
                                method: 'DELETE',
                              });
                              if (!res.ok) throw new Error('Failed to delete');
                              setSegments(prev => prev.filter(s => s.id !== segment.id));
                            } catch (err: any) {
                              alert(err.message);
                            }
                          }
                        }}
                        className="inline-flex items-center justify-center px-3 py-1.5 text-xs font-semibold text-gray-700 bg-white border border-gray-300 rounded-md shadow-sm hover:bg-gray-50 transition-all"
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                  <td className="px-3 py-3 text-sm font-medium text-gray-900 w-[25%]">
                    <div className="line-clamp-3 overflow-hidden">
                      {segment.title}
                    </div>
                  </td>
                  <td className="px-3 py-3 text-sm text-gray-500">{segment.author || 'N/A'}</td>
                  <td className="px-3 py-3 text-center">
                    <span className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-medium ${segment.topic_count > 0 ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'
                      }`}>
                      {segment.topic_count}
                    </span>
                  </td>
                  <td className="px-3 py-3 text-sm text-gray-600 max-w-md truncate">{segment.text}</td>
                  <td className="px-3 py-3 text-xs text-gray-500">{new Date(segment.created_at).toLocaleString()}</td>
                  <td className="px-3 py-3 text-xs text-gray-500">{segment.published_at ? new Date(segment.published_at).toLocaleString() : 'N/A'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </main>
  );
}
