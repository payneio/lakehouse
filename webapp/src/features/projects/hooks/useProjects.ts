import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as api from '@/api';
import { listProjects } from '@/api/projects';
import type { ProjectCreate } from '@/types/api';

export function useProjects() {
  const queryClient = useQueryClient();

  const directories = useQuery({
    queryKey: ['directories'],
    queryFn: listProjects,
  });

  const createProject = useMutation({
    mutationFn: (data: ProjectCreate) => api.createProject(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['directories'] });
    },
  });

  const deleteProject = useMutation({
    mutationFn: ({ relativePath, removeMarker }: { relativePath: string; removeMarker?: boolean }) =>
      api.deleteProject(relativePath, removeMarker),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['directories'] });
    },
  });

  const updateProject = useMutation({
    mutationFn: ({ relativePath, data }: { relativePath: string; data: Partial<ProjectCreate> }) =>
      api.updateProject(relativePath, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['directories'] });
    },
  });

  return {
    directories: directories.data?.projects ?? [],
    isLoading: directories.isLoading,
    error: directories.error,
    createProject,
    deleteProject,
    updateProject,
  };
}

export function useSessions(directoryPath?: string) {
  const sessions = useQuery({
    queryKey: ['sessions', directoryPath],
    queryFn: () => api.listSessions({ project_path: directoryPath }),
    enabled: !!directoryPath,
  });

  return {
    sessions: sessions.data ?? [],
    isLoading: sessions.isLoading,
    error: sessions.error,
  };
}

export function useAllSessions(limit?: number) {
  const sessions = useQuery({
    queryKey: ['sessions', 'all', limit],
    queryFn: () => api.listSessions({ limit }),
  });

  return {
    sessions: sessions.data ?? [],
    isLoading: sessions.isLoading,
    error: sessions.error,
  };
}
