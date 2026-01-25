import {
  copyBundle,
  createBundle,
  deleteBundle,
  listBundles,
  type BundleListItem,
} from "@/api/bundles";
import { MobileMenuButton } from "@/components/layout/MobileMenuButton";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Search } from "lucide-react";
import { useState } from "react";
import { BundleCard } from "./BundleCard";
import { BundleDetailDialog } from "./BundleDetailDialog";
import { BundleEditDialog } from "./BundleEditDialog";
import { BundleSourceDialog } from "./BundleSourceDialog";
import { CopyBundleDialog } from "./CopyBundleDialog";
import { CreateBundleDialog } from "./CreateBundleDialog";
import { DeleteBundleDialog } from "./DeleteBundleDialog";

type SourceFilter = "all" | "user" | "system";

export function BundlesPage() {
  const queryClient = useQueryClient();

  const { data: bundles = [], isLoading } = useQuery({
    queryKey: ["bundles"],
    queryFn: listBundles,
  });

  const [searchQuery, setSearchQuery] = useState("");
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>("all");

  // Dialog states
  const [selectedBundle, setSelectedBundle] = useState<BundleListItem | null>(
    null,
  );
  const [detailDialogOpen, setDetailDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [sourceDialogOpen, setSourceDialogOpen] = useState(false);
  const [copyDialogOpen, setCopyDialogOpen] = useState(false);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);

  // Mutation states
  const [mutationError, setMutationError] = useState<string | null>(null);

  // Copy mutation
  const copyMutation = useMutation({
    mutationFn: ({
      sourceName,
      newName,
    }: {
      sourceName: string;
      newName: string;
    }) => copyBundle(sourceName, newName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["bundles"] });
      setCopyDialogOpen(false);
      setSelectedBundle(null);
      setMutationError(null);
    },
    onError: (error: Error) => {
      setMutationError(error.message);
    },
  });

  // Create mutation
  const createMutation = useMutation({
    mutationFn: createBundle,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["bundles"] });
      setCreateDialogOpen(false);
      setMutationError(null);
    },
    onError: (error: Error) => {
      setMutationError(error.message);
    },
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (name: string) => deleteBundle(name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["bundles"] });
      setDeleteDialogOpen(false);
      setSelectedBundle(null);
      setMutationError(null);
    },
    onError: (error: Error) => {
      setMutationError(error.message);
    },
  });

  // Filter bundles
  const filteredBundles = bundles.filter((bundle) => {
    const matchesSearch = bundle.name
      .toLowerCase()
      .includes(searchQuery.toLowerCase());
    const matchesSource =
      sourceFilter === "all" || bundle.source === sourceFilter;
    return matchesSearch && matchesSource;
  });

  // Event handlers
  const handleView = (bundle: BundleListItem) => {
    setSelectedBundle(bundle);
    setDetailDialogOpen(true);
  };

  const handleCopy = (bundle: BundleListItem) => {
    setSelectedBundle(bundle);
    setMutationError(null);
    setCopyDialogOpen(true);
  };

  const handleEdit = (bundle: BundleListItem) => {
    setSelectedBundle(bundle);
    setEditDialogOpen(true);
  };

  const handleDelete = (bundle: BundleListItem) => {
    setSelectedBundle(bundle);
    setMutationError(null);
    setDeleteDialogOpen(true);
  };

  const handleCopyFromDetail = () => {
    setDetailDialogOpen(false);
    setCopyDialogOpen(true);
  };

  if (isLoading) {
    return <div className="text-muted-foreground p-6">Loading bundles...</div>;
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <MobileMenuButton />
          <h1 className="text-3xl font-bold">Bundles</h1>
        </div>
        <button
          onClick={() => {
            setMutationError(null);
            setCreateDialogOpen(true);
          }}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
        >
          <Plus className="h-4 w-4" />
          Create Bundle
        </button>
      </div>

      {/* Description */}
      <p className="text-muted-foreground">
        Bundles configure agent behavior and capabilities.
      </p>

      {/* Search and Filter */}
      <div className="flex items-center gap-4">
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
        <div className="flex border rounded-md overflow-hidden">
          {(["all", "user", "system"] as const).map((filter) => (
            <button
              key={filter}
              onClick={() => setSourceFilter(filter)}
              className={`px-3 py-2 text-sm ${
                sourceFilter === filter
                  ? "bg-primary text-primary-foreground"
                  : "hover:bg-accent"
              }`}
            >
              {filter === "all" ? "All" : filter === "user" ? "User" : "System"}
            </button>
          ))}
        </div>
      </div>

      {/* Bundle List */}
      <div className="space-y-2">
        {filteredBundles.length === 0 ? (
          <div className="text-center py-12 text-muted-foreground">
            {searchQuery || sourceFilter !== "all"
              ? "No bundles match your search"
              : "No bundles found. Add bundles to ~/.lakehoused/bundles/"}
          </div>
        ) : (
          filteredBundles.map((bundle) => (
            <BundleCard
              key={bundle.name}
              bundle={bundle}
              onView={handleView}
              onCopy={handleCopy}
              onEdit={handleEdit}
              onDelete={handleDelete}
            />
          ))
        )}
      </div>

      {/* Dialogs */}
      <BundleDetailDialog
        bundleName={selectedBundle?.name ?? null}
        bundleSource={selectedBundle?.source ?? null}
        open={detailDialogOpen}
        onClose={() => {
          setDetailDialogOpen(false);
          setSelectedBundle(null);
        }}
        onCopy={handleCopyFromDetail}
      />

      <BundleEditDialog
        bundleName={selectedBundle?.name ?? null}
        open={editDialogOpen}
        onClose={() => {
          setEditDialogOpen(false);
          setSelectedBundle(null);
        }}
      />

      <BundleSourceDialog
        bundleName={selectedBundle?.name ?? null}
        open={sourceDialogOpen}
        onClose={() => {
          setSourceDialogOpen(false);
          setSelectedBundle(null);
        }}
      />

      <CopyBundleDialog
        open={copyDialogOpen}
        sourceBundleName={selectedBundle?.name ?? null}
        sourceBundleSource={selectedBundle?.source ?? null}
        onClose={() => {
          setCopyDialogOpen(false);
          setSelectedBundle(null);
          setMutationError(null);
        }}
        onCopy={(newName) => {
          if (selectedBundle) {
            copyMutation.mutate({ sourceName: selectedBundle.name, newName });
          }
        }}
        isLoading={copyMutation.isPending}
        error={mutationError}
      />

      <CreateBundleDialog
        open={createDialogOpen}
        bundles={bundles}
        onClose={() => {
          setCreateDialogOpen(false);
          setMutationError(null);
        }}
        onCreate={(data) => {
          createMutation.mutate(data);
        }}
        isLoading={createMutation.isPending}
        error={mutationError}
      />

      <DeleteBundleDialog
        open={deleteDialogOpen}
        bundleName={selectedBundle?.name ?? null}
        onClose={() => {
          setDeleteDialogOpen(false);
          setSelectedBundle(null);
          setMutationError(null);
        }}
        onDelete={() => {
          if (selectedBundle) {
            deleteMutation.mutate(selectedBundle.name);
          }
        }}
        isLoading={deleteMutation.isPending}
        error={mutationError}
      />
    </div>
  );
}
