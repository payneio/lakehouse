export type CacheStatus = 'fresh' | 'stale' | 'missing';

export interface CacheTimestamps {
  sourceModified: string | null;
  cacheBuilt: string | null;
}

// @deprecated - Use BundleCacheStatus instead. Bundles replaced profiles in v3.
export interface ProfileCacheStatus {
  profileId: string;
  status: CacheStatus;
  timestamps: CacheTimestamps;
  sourcePath: string;
  cachePath: string | null;
}

export interface BundleCacheStatus {
  bundleId: string;
  status: CacheStatus;
  timestamps: CacheTimestamps;
  sourcePath: string;
  cachePath: string | null;
}

// @deprecated - Collections removed in v3.
export interface CollectionCacheStatus {
  collectionId: string;
  status: CacheStatus;
  timestamps: CacheTimestamps;
  sourcePath: string;
  cachePath: string | null;
  profiles: ProfileCacheStatus[];
}

export interface AllCacheStatus {
  overallStatus: CacheStatus;
  collections: CollectionCacheStatus[];
}

// @deprecated - Use BundleUpdateResult instead. Bundles replaced profiles in v3.
export interface ProfileUpdateResult {
  profileId: string;
  collectionId: string;
  status: CacheStatus;
  action: 'built' | 'skipped' | 'removed';
  message: string;
  error?: string;
}

export interface BundleUpdateResult {
  bundleId: string;
  status: CacheStatus;
  action: 'built' | 'skipped' | 'removed';
  message: string;
  error?: string;
}

export interface CollectionUpdateResult {
  collectionId: string;
  status: CacheStatus;
  action: 'built' | 'skipped' | 'removed';
  message: string;
  profiles: ProfileUpdateResult[];
  error?: string;
}

export interface AllUpdateResult {
  overallStatus: CacheStatus;
  collections: CollectionUpdateResult[];
  summary: {
    totalBuilt: number;
    totalSkipped: number;
    totalRemoved: number;
    totalErrors: number;
  };
}
