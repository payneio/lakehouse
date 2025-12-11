import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as api from '@/api/registries';
import type { RegistryCreateRequest, RegistryUpdateRequest } from '@/api/registries';

export function useRegistries() {
  return useQuery({
    queryKey: ['registries'],
    queryFn: api.listRegistries,
  });
}

export function useRegistry(id: string) {
  return useQuery({
    queryKey: ['registries', id],
    queryFn: () => api.getRegistry(id),
    enabled: !!id,
  });
}

export function useCreateRegistry() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: RegistryCreateRequest) => api.createRegistry(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['registries'] });
    },
  });
}

export function useUpdateRegistry() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: RegistryUpdateRequest }) =>
      api.updateRegistry(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['registries'] });
    },
  });
}

export function useDeleteRegistry() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => api.deleteRegistry(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['registries'] });
    },
  });
}
