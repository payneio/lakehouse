/**
 * React Query hook for managing automations
 */
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listAutomations,
  createAutomation,
  updateAutomation,
  deleteAutomation,
  toggleAutomation,
  executeAutomation,
  type AutomationCreate,
  type AutomationUpdate,
} from "@/api/automations";

/**
 * Hook for managing automations in a project
 */
export function useAutomations(projectId: string) {
  const queryClient = useQueryClient();

  // Fetch automations
  const query = useQuery({
    queryKey: ["automations", projectId],
    queryFn: () => listAutomations(projectId),
    staleTime: 30000, // Consider fresh for 30 seconds
  });

  // Create automation mutation
  const createMutation = useMutation({
    mutationFn: (automation: AutomationCreate) =>
      createAutomation(projectId, automation),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["automations", projectId] });
    },
  });

  // Update automation mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, update }: { id: string; update: AutomationUpdate }) =>
      updateAutomation(projectId, id, update),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["automations", projectId] });
    },
  });

  // Delete automation mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteAutomation(projectId, id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["automations", projectId] });
    },
  });

  // Toggle automation mutation
  const toggleMutation = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      toggleAutomation(projectId, id, enabled),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["automations", projectId] });
    },
  });

  // Execute automation mutation (run now)
  const executeMutation = useMutation({
    mutationFn: (id: string) => executeAutomation(projectId, id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["automations", projectId] });
    },
  });

  return {
    // Data
    automations: query.data?.automations || [],
    total: query.data?.total || 0,

    // Query state
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,

    // Mutations
    create: {
      mutate: createMutation.mutate,
      mutateAsync: createMutation.mutateAsync,
      isPending: createMutation.isPending,
      isError: createMutation.isError,
      error: createMutation.error,
    },
    update: {
      mutate: updateMutation.mutate,
      mutateAsync: updateMutation.mutateAsync,
      isPending: updateMutation.isPending,
      isError: updateMutation.isError,
      error: updateMutation.error,
    },
    delete: {
      mutate: deleteMutation.mutate,
      mutateAsync: deleteMutation.mutateAsync,
      isPending: deleteMutation.isPending,
      isError: deleteMutation.isError,
      error: deleteMutation.error,
    },
    toggle: {
      mutate: toggleMutation.mutate,
      mutateAsync: toggleMutation.mutateAsync,
      isPending: toggleMutation.isPending,
      isError: toggleMutation.isError,
      error: toggleMutation.error,
    },
    execute: {
      mutate: executeMutation.mutate,
      mutateAsync: executeMutation.mutateAsync,
      isPending: executeMutation.isPending,
      isError: executeMutation.isError,
      error: executeMutation.error,
      variables: executeMutation.variables,
    },

    // Refetch
    refetch: query.refetch,
  };
}

/**
 * Hook to get a single automation by ID
 */
export function useAutomation(projectId: string, automationId: string | null) {
  return useQuery({
    queryKey: ["automation", projectId, automationId],
    queryFn: async () => {
      if (!automationId) return null;
      const result = await listAutomations(projectId);
      return result.automations.find((a) => a.id === automationId) || null;
    },
    enabled: !!automationId,
    staleTime: 30000,
  });
}
