import { fetchApi } from './client';
import type { Profile, ProfileDetails, CreateProfileRequest, UpdateProfileRequest } from '@/types/api';

export const listProfiles = () =>
  fetchApi<Profile[]>('/api/v1/profiles/');

export const getProfile = (name: string) =>
  fetchApi<Profile>(`/api/v1/profiles/${name}`);

export const getProfileDetails = (name: string) =>
  fetchApi<ProfileDetails>(`/api/v1/profiles/${name}`);

export const createProfile = (data: CreateProfileRequest) =>
  fetchApi<ProfileDetails>('/api/v1/profiles/', {
    method: 'POST',
    body: JSON.stringify(data),
  });

export const updateProfile = (name: string, data: UpdateProfileRequest) =>
  fetchApi<ProfileDetails>(`/api/v1/profiles/${name}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });

export const deleteProfile = (name: string) =>
  fetchApi<void>(`/api/v1/profiles/${name}`, {
    method: 'DELETE',
  });

export const copyProfile = (sourceName: string, newName: string) =>
  fetchApi<ProfileDetails>(`/api/v1/profiles/${encodeURIComponent(sourceName)}/copy`, {
    method: 'POST',
    body: JSON.stringify({ new_name: newName }),
  });
