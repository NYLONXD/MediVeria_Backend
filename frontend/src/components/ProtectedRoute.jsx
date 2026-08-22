import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import Spinner from './Spinner'
export default function ProtectedRoute({ children }) { const { loading, isAuthenticated } = useAuth(); const location = useLocation(); if (loading) return <Spinner label="Restoring your secure session"/>; return isAuthenticated ? children : <Navigate to="/login" state={{ from: location }} replace/> }
