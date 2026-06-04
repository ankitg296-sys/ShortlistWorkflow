import React, { useState, useEffect } from 'react'
import { createClient } from '@supabase/supabase-js'
import LoginPage from './pages/LoginPage'
import JobsPage from './pages/JobsPage'
import ShortlistPage from './pages/ShortlistPage'

const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_ANON_KEY
)

export default function App() {
  const [user, setUser] = useState(null)
  const [currentPage, setCurrentPage] = useState('jobs')
  const [selectedSearch, setSelectedSearch] = useState(null)

  useEffect(() => {
    supabase.auth.onAuthStateChange((event, session) => {
      setUser(session?.user || null)
    })
  }, [])

  if (!user) {
    return <LoginPage supabase={supabase} />
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 py-4 flex justify-between items-center">
          <h1 className="text-2xl font-bold text-blue-600">ShortList</h1>
          <div className="space-x-4">
            <button
              onClick={() => { setCurrentPage('jobs'); setSelectedSearch(null); }}
              className={`px-4 py-2 rounded ${currentPage === 'jobs' ? 'bg-blue-600 text-white' : 'bg-gray-200'}`}
            >
              Jobs
            </button>
            {selectedSearch && (
              <button
                onClick={() => setCurrentPage('shortlist')}
                className={`px-4 py-2 rounded ${currentPage === 'shortlist' ? 'bg-blue-600 text-white' : 'bg-gray-200'}`}
              >
                Shortlist
              </button>
            )}
            <button
              onClick={() => supabase.auth.signOut()}
              className="px-4 py-2 bg-gray-200 rounded"
            >
              Sign Out
            </button>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-4 py-8">
        {currentPage === 'jobs' && (
          <JobsPage
            supabase={supabase}
            onSelectSearch={(search) => {
              setSelectedSearch(search)
              setCurrentPage('shortlist')
            }}
          />
        )}
        {currentPage === 'shortlist' && selectedSearch && (
          <ShortlistPage supabase={supabase} search={selectedSearch} />
        )}
      </main>
    </div>
  )
}
