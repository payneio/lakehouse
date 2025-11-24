### Collections

Added collections refs stored at:

`$AMPLIFIERD_ROOT/local/share/collection-sources.txt`

Each line: `<collection-id> <source-ref>`

This is the state file for API endpoints that add/remove/list collections.

When a collection ref is modified, the collection is fetched and its profiles are cached.

A collection should be able to be fetched from a git repo (`git+` ref) or file path (any valid fsspec path). When fetched:

- Find the collection's included profiles.
  - If a fsspec ref, look in `<fsspec-resolved path>/profiles/*.md` for valid profile manifests.
  - Check out git ref into `$AMPLIFIERD_ROOT/state/git/<commit hash>/` and look in `profiles/*.md` for valid profile manifests.
- Cache the profile manifests at:
  - `$AMPLIFIERD_ROOT/local/share/profiles/<collection-id>/<profile-id>.md`

Now, any API calls to list or load a profiles can find the profile manifest in the cached location.

Collections aren't really used for anything other than grabbing namespaced profile manifests.

### Profile manifests

#### Schema version

The daemon requires a slightly different profile manifest schema than the CLI. For this reason, the daemon should only consider profile manifests with a `schema-version: 2` key as valid.

The differences between schema version 2 from version 1 are:

- `extends:` keys are not supported by the daemon. The daemon expects full profile manifests.
- Agents are referenced as individual files, not directories with include/exclude patterns.
- Contexts are referenced as refs to directories, not a well-known directory of `./ai_context/` within the collection.

#### Profile storage and caching

Profiles manifests are stored at:

`$AMPLIFIERD_ROOT/share/profiles/<collection-id>/<profile-id>.md`

Profile manifests contain references to the various profile components.References prefixes are: `git+`, or any fsspec path (with relative paths resolved to the daemon CWD).

`extends:` keys in profile manifests are not supported by the daemon. The daemon expects full profile manifests.

When "compiled" all profile refs should be resolved and assets should be cached at:

- state
  - profiles
    - collection
      - profile-uid
        - orchestrator
        - context-manager
        - providers
        - tools
        - hooks
        - agents
        - context

Orchestrator, context-manager, providers, tools, and hooks are all python modules that will be dynamically imported when the profile is loaded.

Errors are atomic, if any part of a profile fails to load, the entire profile load fails.