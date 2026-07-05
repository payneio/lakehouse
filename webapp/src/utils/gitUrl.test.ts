import { describe, it, expect } from 'vitest';
import { toWebUrl } from './gitUrl';

describe('toWebUrl', () => {
  describe('Actual Amplifier Collection URL Formats', () => {
    it('should parse git+https with @branch#subdirectory=path format (developer-expertise)', () => {
      const result = toWebUrl('git+https://github.com/payneio/lakehoused@main#subdirectory=registry/profiles/developer-expertise');
      expect(result).toBe('https://github.com/payneio/lakehoused/tree/main/registry/profiles/developer-expertise');
    });

    it('should parse git+https with @branch#subdirectory=path format (foundation)', () => {
      const result = toWebUrl('git+https://github.com/payneio/lakehoused@main#subdirectory=registry/profiles/foundation');
      expect(result).toBe('https://github.com/payneio/lakehoused/tree/main/registry/profiles/foundation');
    });

    it('should parse git+https with nested subdirectory path', () => {
      const result = toWebUrl('git+https://github.com/payneio/payne-amplifier@main#subdirectory=max_payne_collection/profiles.v2');
      expect(result).toBe('https://github.com/payneio/payne-amplifier/tree/main/max_payne_collection/profiles.v2');
    });
  });

  describe('SSH GitHub URLs', () => {
    it('should handle URL without branch or subdirectory', () => {
      const result = toWebUrl('git@github.com:user/repo.git');
      expect(result).toBe('https://github.com/user/repo');
    });

    it('should handle URL with branch only', () => {
      const result = toWebUrl('git@github.com:user/repo.git@main');
      expect(result).toBe('https://github.com/user/repo/tree/main');
    });

    it('should handle URL with subdirectory only', () => {
      const result = toWebUrl('git@github.com:user/repo.git//src/components');
      expect(result).toBe('https://github.com/user/repo/src/components');
    });

    it('should handle URL with both branch and subdirectory', () => {
      const result = toWebUrl('git@github.com:user/repo.git@develop//src/utils');
      expect(result).toBe('https://github.com/user/repo/tree/develop/src/utils');
    });

    it('should handle URL with nested subdirectory path', () => {
      const result = toWebUrl('git@github.com:user/repo.git@main//src/components/ui/button');
      expect(result).toBe('https://github.com/user/repo/tree/main/src/components/ui/button');
    });
  });

  describe('HTTPS GitHub URLs', () => {
    it('should handle URL without branch or subdirectory', () => {
      const result = toWebUrl('https://github.com/user/repo.git');
      expect(result).toBe('https://github.com/user/repo');
    });

    it('should handle URL with branch only', () => {
      const result = toWebUrl('https://github.com/user/repo.git@main');
      expect(result).toBe('https://github.com/user/repo/tree/main');
    });

    it('should handle URL with subdirectory only', () => {
      const result = toWebUrl('https://github.com/user/repo.git//src/components');
      expect(result).toBe('https://github.com/user/repo/src/components');
    });

    it('should handle URL with both branch and subdirectory', () => {
      const result = toWebUrl('https://github.com/user/repo.git@feature-branch//docs');
      expect(result).toBe('https://github.com/user/repo/tree/feature-branch/docs');
    });
  });

  describe('GitLab URLs', () => {
    it('should use /-/tree/ format for GitLab without subdirectory', () => {
      const result = toWebUrl('git@gitlab.com:user/repo.git@main');
      expect(result).toBe('https://gitlab.com/user/repo/-/tree/main');
    });

    it('should use /-/tree/ format for GitLab with subdirectory', () => {
      const result = toWebUrl('git@gitlab.com:user/repo.git@main//src');
      expect(result).toBe('https://gitlab.com/user/repo/-/tree/main/src');
    });

    it('should handle GitLab HTTPS URLs', () => {
      const result = toWebUrl('https://gitlab.com/user/repo.git@develop//lib');
      expect(result).toBe('https://gitlab.com/user/repo/-/tree/develop/lib');
    });

    it('should handle GitLab URL without branch or subdirectory', () => {
      const result = toWebUrl('git@gitlab.com:user/repo.git');
      expect(result).toBe('https://gitlab.com/user/repo');
    });
  });

  describe('Other Git Hosts', () => {
    it('should handle custom Git host with branch', () => {
      const result = toWebUrl('git@gitea.example.com:org/project.git@main');
      expect(result).toBe('https://gitea.example.com/org/project/tree/main');
    });

    it('should handle Bitbucket-style URLs', () => {
      const result = toWebUrl('git@bitbucket.org:team/repo.git@master//src');
      expect(result).toBe('https://bitbucket.org/team/repo/tree/master/src');
    });
  });

  describe('Edge Cases', () => {
    it('should return null for "local" source', () => {
      const result = toWebUrl('local');
      expect(result).toBe(null);
    });

    it('should return null for URLs without "git"', () => {
      const result = toWebUrl('https://example.com/repo');
      expect(result).toBe(null);
    });

    it('should return null for invalid SSH format', () => {
      const result = toWebUrl('git@invalid');
      expect(result).toBe(null);
    });

    it('should return null for malformed URLs', () => {
      const result = toWebUrl('not-a-git-url');
      expect(result).toBe(null);
    });

    it('should return null for branches with forward slashes (known limitation)', () => {
      // Current implementation doesn't support branch names with forward slashes
      // as the regex pattern [^/]+ explicitly excludes them to avoid ambiguity with subdirectories
      const result = toWebUrl('git@github.com:user/repo.git@feature/new-ui');
      expect(result).toBe(null);
    });

    it('should handle empty string', () => {
      const result = toWebUrl('');
      expect(result).toBe(null);
    });

    it('should handle URLs with subdirectory but no explicit branch', () => {
      const result = toWebUrl('git@github.com:user/repo.git//docs/api');
      expect(result).toBe('https://github.com/user/repo/docs/api');
    });
  });
});
