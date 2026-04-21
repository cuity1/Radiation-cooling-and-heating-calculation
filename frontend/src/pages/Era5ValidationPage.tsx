import { useEffect } from 'react'
import { Navigate } from 'react-router-dom'

export default function Era5ValidationPage() {
  // Redirect to NewJobPage with in_situ_simulation type
  return <Navigate to="/jobs/new?type=in_situ_simulation" replace />
}
