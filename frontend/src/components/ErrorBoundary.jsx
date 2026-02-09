import React from 'react'

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, message: '' }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, message: error ? String(error.message || error) : 'Erro desconhecido' }
  }

  componentDidCatch() {
    // intentionally minimal: we just render a fallback instead of a blank screen
  }

  render() {
    if (!this.state.hasError) return this.props.children

    return (
      <div style={{ padding: 16, fontFamily: 'system-ui, -apple-system, Segoe UI, Roboto, sans-serif' }}>
        <div style={{ maxWidth: 920, margin: '0 auto', background: '#ffffff', border: '1px solid #e5e7eb', borderRadius: 14, padding: 16 }}>
          <div style={{ fontWeight: 900, fontSize: 16, color: '#111827' }}>Ops — ocorreu um erro nesta tela</div>
          <div style={{ marginTop: 6, color: '#6b7280', fontSize: 13 }}>
            Se isso aconteceu ao abrir a lista de clientes, pode ser um erro de dados/configuração.
          </div>
          <div style={{ marginTop: 12, padding: 12, borderRadius: 12, background: '#f8fafc', border: '1px solid #e5e7eb', color: '#0f1724', fontSize: 13, whiteSpace: 'pre-wrap' }}>
            {this.state.message}
          </div>
          <div style={{ marginTop: 12, display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <button
              type="button"
              onClick={() => window.location.reload()}
              style={{ padding: '10px 12px', borderRadius: 12, border: '1px solid rgba(15,23,42,0.10)', background: '#111827', color: '#fff', fontWeight: 900, cursor: 'pointer' }}
            >
              Recarregar
            </button>
            <button
              type="button"
              onClick={() => this.setState({ hasError: false, message: '' })}
              style={{ padding: '10px 12px', borderRadius: 12, border: '1px solid rgba(15,23,42,0.10)', background: '#ffffff', color: '#0f1724', fontWeight: 900, cursor: 'pointer' }}
            >
              Tentar novamente
            </button>
          </div>
        </div>
      </div>
    )
  }
}
