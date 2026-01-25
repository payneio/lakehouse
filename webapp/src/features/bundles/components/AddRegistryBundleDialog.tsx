import { addRegistryBundle } from "@/api/bundles";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, GitBranch, Loader2 } from "lucide-react";
import { useState } from "react";

interface AddRegistryBundleDialogProps {
  open: boolean;
  onClose: () => void;
}

function AddRegistryBundleDialogContent({
  onClose,
}: {
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [gitUrl, setGitUrl] = useState("");
  const [error, setError] = useState<string | null>(null);

  // Mutation for adding registry bundle
  const addMutation = useMutation({
    mutationFn: ({ name, gitUrl }: { name: string; gitUrl: string }) =>
      addRegistryBundle(name, gitUrl),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["bundles"] });
      onClose();
    },
    onError: (error: Error) => {
      setError(error.message);
    },
  });

  // Extract suggested name from git URL
  const suggestedName = (() => {
    if (!gitUrl) return "";
    // Try to extract a reasonable name from the URL
    // e.g., git+https://github.com/owner/repo@main#subdirectory=bundles/my-bundle.md
    const match = gitUrl.match(/subdirectory=.*?([^/]+?)(?:\.(?:md|yaml))?$/);
    if (match) return match[1];
    // Try repo name
    const repoMatch = gitUrl.match(/github\.com\/[^/]+\/([^/@#]+)/);
    if (repoMatch) return repoMatch[1];
    return "";
  })();

  // Use suggested name if user hasn't typed anything
  const effectiveName = name || suggestedName;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // Validate name format
    if (!/^[a-z0-9-]+$/.test(effectiveName)) {
      setError("Name must be kebab-case (lowercase letters, numbers, hyphens)");
      return;
    }

    // Validate git URL format
    if (!gitUrl.startsWith("git+")) {
      setError("Git URL must start with 'git+' (e.g., git+https://github.com/...)");
      return;
    }

    addMutation.mutate({ name: effectiveName, gitUrl });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="flex items-center gap-2 text-muted-foreground mb-2">
        <GitBranch className="h-4 w-4" />
        <span className="text-sm">
          Add a bundle from a git repository to your system bundles
        </span>
      </div>

      {/* Git URL input */}
      <div>
        <label
          htmlFor="gitUrl"
          className="block text-sm font-medium mb-1"
        >
          Git URL
        </label>
        <input
          id="gitUrl"
          type="text"
          value={gitUrl}
          onChange={(e) => setGitUrl(e.target.value)}
          placeholder="git+https://github.com/owner/repo@branch#subdirectory=path/to/bundle.md"
          className="w-full px-3 py-2 border rounded-md text-sm font-mono"
          autoFocus
        />
        <p className="mt-1 text-xs text-muted-foreground">
          Format: git+https://github.com/owner/repo@branch#subdirectory=path
        </p>
      </div>

      {/* Name input */}
      <div>
        <label htmlFor="name" className="block text-sm font-medium mb-1">
          Bundle Name
        </label>
        <input
          id="name"
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value.toLowerCase())}
          placeholder={suggestedName || "my-bundle"}
          className="w-full px-3 py-2 border rounded-md text-sm"
        />
        <p className="mt-1 text-xs text-muted-foreground">
          Kebab-case name (e.g., my-custom-bundle)
          {suggestedName && !name && (
            <span className="ml-1 text-primary">
              — will use "{suggestedName}"
            </span>
          )}
        </p>
      </div>

      {/* Error message */}
      {error && (
        <div className="flex items-center gap-2 text-destructive text-sm">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      )}

      {/* Actions */}
      <div className="flex justify-end gap-2 pt-2">
        <button
          type="button"
          onClick={onClose}
          className="px-4 py-2 text-sm border rounded-md hover:bg-accent"
          disabled={addMutation.isPending}
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={!effectiveName || !gitUrl || addMutation.isPending}
          className="flex items-center gap-2 px-4 py-2 text-sm bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50"
        >
          {addMutation.isPending && (
            <Loader2 className="h-4 w-4 animate-spin" />
          )}
          Add Bundle
        </button>
      </div>
    </form>
  );
}

export function AddRegistryBundleDialog({
  open,
  onClose,
}: AddRegistryBundleDialogProps) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50"
        onClick={onClose}
      />

      {/* Dialog */}
      <div className="relative bg-background rounded-lg shadow-lg w-full max-w-lg mx-4 p-6">
        <h2 className="text-lg font-semibold mb-4">Add Bundle from Git</h2>
        <AddRegistryBundleDialogContent onClose={onClose} />
      </div>
    </div>
  );
}
