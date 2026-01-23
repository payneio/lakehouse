import { useQuery } from '@tanstack/react-query';
import { Package, Search } from 'lucide-react';
import { useState } from 'react';
import { listBundles } from '@/api/bundles';
import { MobileMenuButton } from '@/components/layout/MobileMenuButton';

export function BundlesPage() {
  const { data: bundles = [], isLoading } = useQuery({
    queryKey: ['bundles'],
    queryFn: listBundles,
  });

  const [searchQuery, setSearchQuery] = useState('');

  // Filter bundles by search query
  const filteredBundles = bundles.filter(bundle =>
    bundle.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  if (isLoading) {
    return <div className="text-muted-foreground p-6">Loading bundles...</div>;
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <MobileMenuButton />
        <h1 className="text-3xl font-bold">Bundles</h1>
      </div>

      {/* Description */}
      <p className="text-muted-foreground">
        Bundles configure agent behavior and capabilities. They are loaded from{' '}
        <code className="px-1.5 py-0.5 bg-muted rounded text-sm">~/.amplifierd/bundles/</code>{' '}
        and configured registries.
      </p>

      {/* Search */}
      <div className="flex items-center gap-2">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search bundles..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border rounded-md"
          />
        </div>
      </div>

      {/* Bundle List */}
      <div className="space-y-2">
        {filteredBundles.length === 0 ? (
          <div className="text-center py-12 text-muted-foreground">
            {searchQuery
              ? 'No bundles match your search'
              : 'No bundles found. Add bundles to ~/.amplifierd/bundles/'}
          </div>
        ) : (
          filteredBundles.map((bundle) => (
            <div
              key={bundle.name}
              className="flex items-center gap-3 p-4 border rounded-lg hover:bg-accent/50 transition-colors"
            >
              <Package className="h-5 w-5 text-muted-foreground shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="font-medium">{bundle.name}</div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
