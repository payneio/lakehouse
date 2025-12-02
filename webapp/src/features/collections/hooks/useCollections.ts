import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as api from '@/api';

export function useCollections() {
  const collections = useQuery({
    queryKey: ['collections'],
    queryFn: api.listCollections,
  });

  return {
    collections: collections.data ?? [],
    isLoading: collections.isLoading,
    error: collections.error,
  };
}

export function useProfiles() {
  const profiles = useQuery({
    queryKey: ['profiles'],
    queryFn: api.listProfiles,
  });

  return {
    profiles: profiles.data ?? [],
    isLoading: profiles.isLoading,
    error: profiles.error,
  };
}

export function useCacheStatus() {
  return useQuery({
    queryKey: ['cache', 'status'],
    queryFn: api.getCacheStatus,
    refetchInterval: 30000,
  });
}

export function useCollectionStatus(identifier: string) {
  return useQuery({
    queryKey: ['cache', 'status', 'collections', identifier],
    queryFn: () => api.getCollectionStatus(identifier),
    refetchInterval: 30000,
  });
}

export function useUpdateCollection() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ identifier, ...params }: { identifier: string; checkOnly?: boolean; force?: boolean }) =>
      api.updateCollection(identifier, params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cache', 'status'] });
      queryClient.invalidateQueries({ queryKey: ['collections'] });
    },
  });
}

export function useUpdateAllCollections() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: api.updateAllCollections,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cache', 'status'] });
      queryClient.invalidateQueries({ queryKey: ['collections'] });
    },
  });
}

export function useUpdateProfile() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ collectionId, profileName, ...params }: {
      collectionId: string;
      profileName: string;
      checkOnly?: boolean;
      force?: boolean;
    }) => api.updateProfile(collectionId, profileName, params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cache', 'status'] });
      queryClient.invalidateQueries({ queryKey: ['profiles'] });
    },
  });
}

export function useMountCollection() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: api.mountCollection,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['collections'] });
    },
  });
}

export function useUnmountCollection() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: api.unmountCollection,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['collections'] });
    },
  });
}
