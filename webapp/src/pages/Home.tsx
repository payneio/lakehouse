import { BASE_URL } from '@/api/client';
import { useEffect, useState } from 'react';

export function HomePage() {
  const [apiStatus, setApiStatus] = useState<'checking' | 'connected' | 'error'>('checking');
  const [apiVersion, setApiVersion] = useState<string>('');
  const [dataPath, setDataPath] = useState<string>('');

  useEffect(() => {
    // Check API connection on mount
    const checkConnection = async () => {
      try {
        const response = await fetch(`${BASE_URL}/api/v1/status`, {
          mode: 'cors',
        });

        const data = await response.json();
        setApiStatus('connected');
        setApiVersion(data.version || 'unknown');
        setDataPath(data.rootDir || '');
      } catch {
        setApiStatus('error');
      }
    };

    checkConnection();
  }, []);

  const getStatusColor = () => {
    switch (apiStatus) {
      case 'connected': return 'text-green-600';
      case 'error': return 'text-red-600';
      default: return 'text-yellow-600';
    }
  };

  const getStatusText = () => {
    switch (apiStatus) {
      case 'connected': return 'Connected';
      case 'error': return 'Disconnected';
      default: return 'Checking...';
    }
  };

  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold mb-4">Welcome to Amplifier</h1>

      <div className="border rounded-lg p-4 bg-muted/50">
        <h2 className="text-lg font-semibold mb-2">Connection Info</h2>
        <div className="space-y-2">
          <div className="space-y-1 text-sm">
            <h3 className="font-medium">Frontend (This Page)</h3>
            <div>
              <span className="text-muted-foreground">URL: </span>
              <span className="font-mono">{typeof window !== 'undefined' ? window.location.href : ''}</span>
            </div>
            <div>
              <span className="text-muted-foreground">Port: </span>
              <span className="font-mono">{typeof window !== 'undefined' ? window.location.port : ''}</span>
            </div>
          </div>
          <div className="border-t pt-2 space-y-1 text-sm">
            <h3 className="font-medium">API Backend</h3>
            <div>
              <span className="text-muted-foreground">Configured Endpoint: </span>
              <span className="font-mono">{BASE_URL}</span>
            </div>
            <div>
              <span className="text-muted-foreground">Env Variable: </span>
              <span className="font-mono">{import.meta.env.VITE_API_URL || 'not set'}</span>
            </div>
            <div>
              <span className="text-muted-foreground">Status: </span>
              <span className={getStatusColor()}>{getStatusText()}</span>
            </div>
            {apiVersion && (
              <div>
                <span className="text-muted-foreground">Version: </span>
                <span>{apiVersion}</span>
              </div>
            )}
            {dataPath && (
              <div>
                <span className="text-muted-foreground">Data Path: </span>
                <span className="font-mono">{dataPath}</span>
              </div>
            )}
            {apiStatus === 'error' && (
              <div className="mt-2 p-2 bg-destructive/10 text-destructive text-xs rounded">
                Cannot connect to API. Check browser console for details.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
