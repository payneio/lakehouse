import {
  copyAssistant,
  createAssistant,
  deleteAssistant,
  listAssistants,
  type AssistantListItem,
} from "@/api/assistants";
import { MobileMenuButton } from "@/components/layout/MobileMenuButton";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Search } from "lucide-react";
import { useState } from "react";
import { AssistantCard } from "./AssistantCard";
import { AssistantDetailDialog } from "./AssistantDetailDialog";
import { AssistantSourceDialog } from "./AssistantSourceDialog";
import { CopyAssistantDialog } from "./CopyAssistantDialog";
import { CreateAssistantDialog } from "./CreateAssistantDialog";
import { DeleteAssistantDialog } from "./DeleteAssistantDialog";

export function AssistantsPage() {
  const queryClient = useQueryClient();

  const { data: assistants = [], isLoading } = useQuery({
    queryKey: ["assistants"],
    queryFn: listAssistants,
  });

  const [searchQuery, setSearchQuery] = useState("");

  // Dialog states
  const [selectedAssistant, setSelectedAssistant] = useState<AssistantListItem | null>(
    null,
  );
  const [detailDialogOpen, setDetailDialogOpen] = useState(false);
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
    }) => copyAssistant(sourceName, newName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["assistants"] });
      setCopyDialogOpen(false);
      setSelectedAssistant(null);
      setMutationError(null);
    },
    onError: (error: Error) => {
      setMutationError(error.message);
    },
  });

  // Create mutation
  const createMutation = useMutation({
    mutationFn: createAssistant,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["assistants"] });
      setCreateDialogOpen(false);
      setMutationError(null);
    },
    onError: (error: Error) => {
      setMutationError(error.message);
    },
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (name: string) => deleteAssistant(name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["assistants"] });
      setDeleteDialogOpen(false);
      setSelectedAssistant(null);
      setMutationError(null);
    },
    onError: (error: Error) => {
      setMutationError(error.message);
    },
  });

  // Filter and sort assistants alphabetically
  const filteredAssistants = assistants
    .filter((assistant) =>
      assistant.name.toLowerCase().includes(searchQuery.toLowerCase()),
    )
    .sort((a, b) => a.name.localeCompare(b.name));

  // Event handlers
  const handleView = (assistant: AssistantListItem) => {
    setSelectedAssistant(assistant);
    setDetailDialogOpen(true);
  };

  const handleDeleteFromDetail = () => {
    setDetailDialogOpen(false);
    setMutationError(null);
    setDeleteDialogOpen(true);
  };

  const handleCopyFromDetail = () => {
    setDetailDialogOpen(false);
    setCopyDialogOpen(true);
  };

  const handleRenameFromDetail = (newName: string) => {
    // Update selected assistant with new name so dialog shows correct name
    if (selectedAssistant) {
      setSelectedAssistant({ ...selectedAssistant, name: newName });
    }
  };

  if (isLoading) {
    return <div className="text-muted-foreground p-6">Loading assistants...</div>;
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <MobileMenuButton />
          <h1 className="text-3xl font-bold">Assistants</h1>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              setMutationError(null);
              setCreateDialogOpen(true);
            }}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
          >
            <Plus className="h-4 w-4" />
            Create Assistant
          </button>
        </div>
      </div>

      {/* Description */}
      <p className="text-muted-foreground">
        Assistants configure agent behavior and capabilities.
      </p>

      {/* Search */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search assistants..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border rounded-md"
          />
        </div>
      </div>

      {/* Assistant Grid */}
      {filteredAssistants.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          {searchQuery
            ? "No assistants match your search"
            : "No assistants found in your assistant store."}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-[repeat(auto-fill,minmax(250px,1fr))] gap-4">
          {filteredAssistants.map((assistant) => (
            <AssistantCard key={assistant.name} assistant={assistant} onView={handleView} />
          ))}
        </div>
      )}

      {/* Dialogs */}
      <AssistantDetailDialog
        assistantName={selectedAssistant?.name ?? null}
        open={detailDialogOpen}
        onClose={() => {
          setDetailDialogOpen(false);
          setSelectedAssistant(null);
        }}
        onCopy={handleCopyFromDetail}
        onDelete={handleDeleteFromDetail}
        onRename={handleRenameFromDetail}
      />

      <AssistantSourceDialog
        assistantName={selectedAssistant?.name ?? null}
        open={sourceDialogOpen}
        onClose={() => {
          setSourceDialogOpen(false);
          setSelectedAssistant(null);
        }}
      />

      <CopyAssistantDialog
        open={copyDialogOpen}
        sourceAssistantName={selectedAssistant?.name ?? null}
        onClose={() => {
          setCopyDialogOpen(false);
          setSelectedAssistant(null);
          setMutationError(null);
        }}
        onCopy={(newName) => {
          if (selectedAssistant) {
            copyMutation.mutate({ sourceName: selectedAssistant.name, newName });
          }
        }}
        isLoading={copyMutation.isPending}
        error={mutationError}
      />

      <CreateAssistantDialog
        open={createDialogOpen}
        assistants={assistants}
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

      <DeleteAssistantDialog
        open={deleteDialogOpen}
        assistantName={selectedAssistant?.name ?? null}
        onClose={() => {
          setDeleteDialogOpen(false);
          setSelectedAssistant(null);
          setMutationError(null);
        }}
        onDelete={() => {
          if (selectedAssistant) {
            deleteMutation.mutate(selectedAssistant.name);
          }
        }}
        isLoading={deleteMutation.isPending}
        error={mutationError}
      />
    </div>
  );
}
