import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as api from '@/api';
import type { AmplifiedDirectoryCreate } from '@/types/api';

export function useDirectories() {
  const queryClient = useQueryClient();

  const directories = useQuery({
    queryKey: ['directories'],
    queryFn: api.listDirectories,
  });

  const createDirectory = useMutation({
    mutationFn: (data: AmplifiedDirectoryCreate) => api.createDirectory(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['directories'] });
    },
  });

  const deleteDirectory = useMutation({
    mutationFn: ({ relativePath, removeMarker }: { relativePath: string; removeMarker?: boolean }) =>
      api.deleteDirectory(relativePath, removeMarker),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['directories'] });
    },
  });

  const updateDirectory = useMutation({
    mutationFn: ({ relativePath, data }: { relativePath: string; data: Partial<AmplifiedDirectoryCreate> }) =>
      api.updateDirectory(relativePath, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['directories'] });
    },
  });

  return {
    directories: directories.data?.directories ?? [],
    isLoading: directories.isLoading,
    error: directories.error,
    createDirectory,
    deleteDirectory,
    updateDirectory,
  };
}

export function useSessions(directoryPath?: string) {
  const sessions = useQuery({
    queryKey: ['sessions', directoryPath],
    queryFn: () => api.listSessions({ amplified_dir: directoryPath }),
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
