import { Link } from 'react-router-dom'
export default function NotFound() { return <main className="not-found"><p className="eyebrow">404</p><h1>This page is unavailable.</h1><Link className="primary-button" to="/dashboard">Go to dashboard <span>→</span></Link></main> }
