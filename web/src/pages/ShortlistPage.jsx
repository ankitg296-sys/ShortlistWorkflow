import React, { useState, useEffect } from 'react'

export default function ShortlistPage({ supabase, search }) {
  const [shortlist, setShortlist] = useState([])
  const [loading, setLoading] = useState(true)
  const [topN, setTopN] = useState(10)

  useEffect(() => {
    loadShortlist()
  }, [search, topN])

  const loadShortlist = async () => {
    setLoading(true)
    try {
      // This would call the backend API in a real app
      // For now, we'll just show the structure
      console.log('Would fetch shortlist for search:', search)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold">Shortlist: {search.job_title}</h2>
        <div>
          <label className="mr-2">Show top:</label>
          <select
            value={topN}
            onChange={(e) => setTopN(parseInt(e.target.value))}
            className="px-3 py-1 border rounded"
          >
            {[5, 10, 15, 20].map((n) => (
              <option key={n} value={n}>{n}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="bg-yellow-50 border border-yellow-200 p-4 rounded">
        <p className="text-sm">
          ⚠️ <strong>Decision Support:</strong> This shortlist is AI-generated. A human always makes the final hiring decision.
        </p>
      </div>

      {loading ? (
        <div>Loading shortlist...</div>
      ) : shortlist.length === 0 ? (
        <div className="bg-white p-8 rounded-lg shadow text-center text-gray-600">
          No candidates yet. Run a search from the Jobs page.
        </div>
      ) : (
        <div className="space-y-4">
          {shortlist.map((candidate, rank) => (
            <div key={candidate.id} className="bg-white p-6 rounded-lg shadow">
              <div className="flex justify-between items-start mb-4">
                <div>
                  <span className="inline-block bg-blue-600 text-white px-3 py-1 rounded-full text-sm font-bold mr-2">
                    #{rank + 1}
                  </span>
                  <span className="text-2xl font-bold">
                    {(candidate.overall_score * 100).toFixed(0)}%
                  </span>
                </div>
              </div>

              <p className="text-gray-700 mb-4">{candidate.summary}</p>

              <div className="space-y-2 mb-4">
                <h4 className="font-semibold">Criteria Breakdown:</h4>
                {candidate.criteria_scores?.map((crit, i) => (
                  <div key={i} className="flex justify-between text-sm">
                    <span>{crit.name}</span>
                    <span className="font-semibold">{(crit.score * 100).toFixed(0)}%</span>
                  </div>
                ))}
              </div>

              {candidate.flags?.length > 0 && (
                <div className="mb-4 p-2 bg-red-50 rounded">
                  {candidate.flags.map((flag, i) => (
                    <div key={i} className="text-sm text-red-700">
                      ⚠️ {flag}
                    </div>
                  ))}
                </div>
              )}

              <button className="text-blue-600 hover:underline text-sm">
                View Full CV
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
