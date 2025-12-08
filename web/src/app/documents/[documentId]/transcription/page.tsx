'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';

export default function TranscriptionWorkbenchPage() {
  const params = useParams();
  const documentId = params.documentId as string;

  return (
    <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
      <div className="px-4 py-6 sm:px-0">
        <div className="mb-6">
          <Link
            href="/documents"
            className="text-indigo-600 hover:text-indigo-800 text-sm flex items-center gap-1"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Back to Documents
          </Link>
        </div>

        <div className="bg-white shadow sm:rounded-lg">
          <div className="px-6 py-8">
            <div className="text-center">
              <div className="mx-auto flex items-center justify-center h-16 w-16 rounded-full bg-purple-100 mb-4">
                <svg
                  className="h-8 w-8 text-purple-600"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"
                  />
                </svg>
              </div>
              <h1 className="text-2xl font-bold text-gray-900 mb-2">Transcription Workbench</h1>
              <p className="text-gray-500 mb-4">Coming soon</p>
              <div className="bg-gray-50 rounded-lg p-4 inline-block">
                <p className="text-sm text-gray-600">
                  <span className="font-medium">Document ID:</span>{' '}
                  <code className="bg-gray-200 px-2 py-1 rounded text-xs">{documentId}</code>
                </p>
              </div>
              <p className="text-sm text-gray-500 mt-6 max-w-md mx-auto">
                This workbench will allow you to manage audio transcription, review and edit
                transcripts, and trigger transcription jobs via OpenAI Whisper or AssemblyAI.
              </p>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}

