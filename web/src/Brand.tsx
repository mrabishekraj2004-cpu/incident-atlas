import { Link } from 'react-router-dom'

export function Brand({ className = '' }: { className?: string }) {
  return <Link to="/" className={`brand ${className}`.trim()} aria-label="Incident Atlas home">
    <span className="brand-wordmark">
      <small>EVIDENCE-LED INCIDENT RESPONSE</small>
      <strong><span>Incident</span><em>Atlas</em></strong>
    </span>
  </Link>
}
