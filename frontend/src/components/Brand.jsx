import { Link } from 'react-router-dom'
export default function Brand({ light = false }) { return <Link to="/" className={`brand ${light ? 'brand--light' : ''}`} aria-label="MediVeria home"><span className="brand__mark">M</span><span>MediVeria</span></Link> }
