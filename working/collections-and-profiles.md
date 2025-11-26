# Amplifierd handling of collections and profile manifests

## Collections

Collections are just namespaced lists of profile manifests.

This is the state file for API endpoints that add/remove/list collections.

`$AMPLIFIERD_SHARE_DIR/collection.yaml`

When a collection ref is modified, the collection is fetched and its profiles are cached.

A collection should be able to be fetched from a git repo (`git+` ref) or file path (any valid fsspec path). When fetched:

- Find the collection's included profiles.
  - If a fsspec ref, look in `<fsspec-resolved path>/*.md` for valid profile manifests.
  - Check out git ref into `$AMPLIFIERD_CACHE_DIR/git/<commit hash>/` and look in `*.md` for valid profile manifests.
- Save the discovered profile manifests at:
  - `$AMPLIFIERD_SHARE_DIR/profiles/<collection-id>/<profile-id>/<profile-id>.md`

Now, any API calls to list or load a profiles can find the profile manifest in the share location.

## Profile manifests

### Schema version

The daemon requires a slightly different profile manifest schema than the CLI. For this reason, the daemon should only consider profile manifests with a `schema_version: 2` key as valid.

The differences between schema version 2 from version 1 are:

- `extends:` keys are not supported by the daemon. The daemon expects full profile manifests.
- Agents are referenced as individual files, not directories with include/exclude patterns.
- Contexts are referenced as refs to directories, not a well-known directory of `./ai_context/` within the collection.

### Profile storage and caching

Profiles manifests are stored at:

`$AMPLIFIERD_SHARE_DIR/profiles/<collection-id>/<profile-id>/<profile-id>.md`

Profile manifests contain references to the various profile components. Reference prefixes are: `git+`, or any fsspec path (with relative paths resolved to the daemon CWD).

When "compiled" all profile refs should be resolved, assets gathered, and persisted at:

- $AMPLIFIERD_SHARE_DIR/
  - profiles
    - <collection-id>
      - <profile-id>
        - <profile-id>.md
        - orchestrator/
        - context-manager/
        - providers/
        - tools/
        - hooks/
        - agents/
        - context/

Orchestrator, context-manager, providers, tools, and hooks are all python modules that will be dynamically imported when the profile is loaded.

agents and context are just data assets that will be read by the profile's orchestrator and agents at runtime.

Resolution involves:
- if a `git+` path, cloning the git ref into a cache, `$AMPLIFIERD_CACHE_DIR/git/<commit hash>/`, and returning the path to the cache.
- if a local path, just returning it.

Either way, after resolution, the assets will be copied to the share dir.

Errors are atomic, if any part of a profile fails to load, the entire profile load fails.
