import React, { useState, useEffect } from 'react'

export default function JobsPage({ supabase, onSelectSearch }) {
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(true)
  const [newJobTitle, setNewJobTitle] = useState('')
  const [newJobDesc, setNewJobDesc] = useState('')

  useEffect(() => {
    loadJobs()
  }, [])

  const loadJobs = async () => {
    try {
      const { data, error } = await supabase
        .from('jobs')
        .select('*')
        .eq('status', 'active')
      if (error) throw error
      setJobs(data || [])
    } finally {
      setLoading(false)
    }
  }

  const handleCreateJob = async (e) => {
    e.preventDefault()
    try {
      const { data, error } = await supabase
        .from('jobs')
        .insert([{ title: newJobTitle, description: newJobDesc }])
        .select()
      if (error) throw error
      setNewJobTitle('')
      setNewJobDesc('')
      loadJobs()
    } catch (err) {
      alert('Error creating job: ' + err.message)
    }
  }

  if (loading) return <div>Loading...</div>

  return (
    <div className="space-y-6">
      <div className="bg-white p-6 rounded-lg shadow">
        <h2 className="text-xl font-bold mb-4">Create Job</h2>
        <form onSubmit={handleCreateJob} className="space-y-4">
          <input
            type="text"
            placeholder="Job Title"
            value={newJobTitle}
            onChange={(e) => setNewJobTitle(e.target.value)}
            className="w-full px-4 py-2 border rounded"
            required
          />
          <textarea
            placeholder="Job Description"
            value={newJobDesc}
            onChange={(e) => setNewJobDesc(e.target.value)}
            className="w-full px-4 py-2 border rounded h-24"
          />
          <button type="submit" className="bg-blue-600 text-white px-4 py-2 rounded">
            Create Job
          </button>
        </form>
      </div>

      <div className="space-y-4">
        <h2 className="text-xl font-bold">Your Jobs</h2>
        {jobs.length === 0 ? (
          <p>No jobs yet.</p>
        ) : (
          jobs.map((job) => (
            <div key={job.id} className="bg-white p-4 rounded-lg shadow">
              <h3 className="font-bold">{job.title}</h3>
              <p className="text-gray-600 text-sm">{job.description}</p>
              <button
                onClick={() => onSelectSearch({ job_id: job.id, job_title: job.title })}
                className="mt-2 bg-blue-600 text-white px-3 py-1 rounded text-sm"
              >
                Run Search
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
