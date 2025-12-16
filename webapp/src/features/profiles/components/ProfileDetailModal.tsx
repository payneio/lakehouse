import { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Copy, Edit, Trash2 } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import * as api from '@/api';
import type { ModuleConfig, ProfileDetails } from '@/types/api';
import { CopyProfileDialog } from './CopyProfileDialog';

interface ProfileDetailModalProps {
  profileName: string | null;
  onClose: () => void;
  onEdit?: (profile: ProfileDetails) => void;
  onDelete?: (profileName: string, source: string) => void;
}

export function ProfileDetailModal({ profileName, onClose, onEdit, onDelete }: ProfileDetailModalProps) {
  const [showCopyDialog, setShowCopyDialog] = useState(false);

  const { data: profile, isLoading } = useQuery({
    queryKey: ['profile-detail', profileName],
    queryFn: () => api.getProfileDetails(profileName!),
    enabled: !!profileName,
  });

  const handleCopySuccess = () => {
    onClose();
  };

  if (!profileName) return null;

  const isLocal = profile?.sourceType === 'local';

  return (
    <Dialog open={!!profileName} onOpenChange={onClose}>
      <DialogContent className="max-w-7xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <div className="flex items-center justify-between">
            <DialogTitle>Profile Details</DialogTitle>
            {profile && (onEdit || onDelete) && (
              <div className="flex gap-2">
                <button
                  onClick={() => setShowCopyDialog(true)}
                  className="p-2 hover:bg-accent rounded-md"
                  title="Copy profile"
                >
                  <Copy className="h-4 w-4" />
                </button>
                {isLocal && onEdit && (
                  <button
                    onClick={() => onEdit(profile)}
                    className="p-2 hover:bg-accent rounded-md"
                    title="Edit profile"
                  >
                    <Edit className="h-4 w-4" />
                  </button>
                )}
                {isLocal && onDelete && (
                  <button
                    onClick={() => onDelete(profile.name, profile.source)}
                    className="p-2 hover:bg-accent rounded-md text-destructive"
                    title="Delete profile"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                )}
              </div>
            )}
          </div>
        </DialogHeader>

        {isLoading ? (
          <div className="text-muted-foreground">Loading...</div>
        ) : profile ? (
          <div className="space-y-6">
            <div>
              <h3 className="text-2xl font-bold">{profile.name}</h3>
              <p className="text-sm text-muted-foreground">v{profile.version}</p>
              <p className="mt-2">{profile.description}</p>
              <div className="flex gap-2 mt-2">
                <span className="text-xs px-2 py-1 bg-muted rounded">
                  Schema v{profile.schemaVersion}
                </span>
                {profile.isActive && (
                  <span className="text-xs px-2 py-1 bg-primary/10 text-primary rounded">
                    Active
                  </span>
                )}
                <span className="text-xs px-2 py-1 bg-muted rounded">
                  {profile.source}
                </span>
                {isLocal && (
                  <span className="text-xs px-2 py-1 bg-green-100 text-green-800 rounded">
                    Local
                  </span>
                )}
              </div>
            </div>

            {profile.session?.orchestrator && (
              <div>
                <h4 className="font-semibold mb-2">Orchestrator</h4>
                <ModuleDisplay module={profile.session.orchestrator} />
              </div>
            )}

            {profile.session?.contextManager && (
              <div>
                <h4 className="font-semibold mb-2">Context Manager</h4>
                <ModuleDisplay module={profile.session.contextManager} />
              </div>
            )}

            {profile.providers.length > 0 && (
              <div>
                <h4 className="font-semibold mb-2">Providers ({profile.providers.length})</h4>
                <div className="space-y-2">
                  {profile.providers.map((p, i) => (
                    <ModuleDisplay key={i} module={p} />
                  ))}
                </div>
              </div>
            )}

            {profile.behaviors && profile.behaviors.length > 0 && (
              <div>
                <h4 className="font-semibold mb-2">Behaviors ({profile.behaviors.length})</h4>
                <div className="space-y-2">
                  {profile.behaviors.map((behavior, i) => (
                    <div key={i} className="border rounded-lg p-3 bg-muted/50">
                      <div className="font-mono text-sm font-semibold">{behavior.id}</div>
                      {behavior.source && (
                        <div className="text-xs text-muted-foreground mt-1 break-all">
                          Source: {behavior.source}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {profile.instruction && (
              <div>
                <h4 className="font-semibold mb-2">System Instruction</h4>
                <div className="border rounded-lg p-4 bg-muted/50">
                  <pre className="text-sm whitespace-pre-wrap font-mono overflow-x-auto max-h-96 overflow-y-auto">
                    {profile.instruction}
                  </pre>
                </div>
              </div>
            )}

            {profile.inheritanceChain && profile.inheritanceChain.length > 0 && (
              <div>
                <h4 className="font-semibold mb-2">Inheritance Chain</h4>
                <div className="flex items-center gap-2">
                  {profile.inheritanceChain.map((parent, i) => (
                    <div key={i} className="flex items-center gap-2">
                      {i > 0 && <span className="text-muted-foreground">→</span>}
                      <span className="text-sm font-mono px-2 py-1 bg-muted rounded">
                        {parent}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="text-muted-foreground">Profile not found</div>
        )}
      </DialogContent>

      {profileName && (
        <CopyProfileDialog
          sourceName={showCopyDialog ? profileName : null}
          onClose={() => setShowCopyDialog(false)}
          onSuccess={handleCopySuccess}
        />
      )}
    </Dialog>
  );
}

function ModuleDisplay({ module }: { module: ModuleConfig }) {
  return (
    <div className="border rounded-lg p-3 bg-muted/50">
      <div className="font-mono text-sm font-semibold">{module.module}</div>
      {module.source && (
        <div className="text-xs text-muted-foreground mt-1 break-all">
          {module.source}
        </div>
      )}
      {module.config && Object.keys(module.config).length > 0 && (
        <details className="mt-2">
          <summary className="text-xs cursor-pointer text-muted-foreground hover:text-foreground">
            Configuration
          </summary>
          <pre className="text-xs mt-1 overflow-x-auto bg-background p-2 rounded">
            {JSON.stringify(module.config, null, 2)}
          </pre>
        </details>
      )}
    </div>
  );
}
