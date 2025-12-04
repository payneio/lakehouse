import type { AmplifiedDirectory } from "@/types/api";

export interface TreeNode {
  name: string;
  fullPath: string;
  directory: AmplifiedDirectory | null;
  children: TreeNode[];
  isExpanded: boolean;
  depth: number;
}

export function buildDirectoryTree(directories: AmplifiedDirectory[]): TreeNode[] {
  const nodeMap = new Map<string, TreeNode>();
  const dirMap = new Map<string, AmplifiedDirectory>();

  // Index directories by path for lookup
  for (const dir of directories) {
    dirMap.set(dir.relative_path, dir);
  }

  // Create all nodes first
  for (const dir of directories) {
    const segments = dir.relative_path.split("/");

    for (let i = 0; i < segments.length; i++) {
      const path = segments.slice(0, i + 1).join("/");

      if (!nodeMap.has(path)) {
        const matchingDir = dirMap.get(path);
        const segment = segments[i];
        const displayName = matchingDir?.metadata?.name || (segment === "." ? "Root" : segment);

        nodeMap.set(path, {
          name: displayName,
          fullPath: path,
          directory: i === segments.length - 1 ? dir : null,
          children: [],
          isExpanded: false,
          depth: i,
        });
      }
    }
  }

  // Build parent-child relationships
  const roots: TreeNode[] = [];

  for (const node of nodeMap.values()) {
    const parentPath = node.fullPath.split("/").slice(0, -1).join("/");

    if (parentPath) {
      const parent = nodeMap.get(parentPath);
      if (parent) {
        parent.children.push(node);
      }
    } else {
      roots.push(node);
    }
  }

  // Sort with root projects first, then alphabetically
  function sortNodes(a: TreeNode, b: TreeNode): number {
    const aIsRoot = a.directory?.relative_path === ".";
    const bIsRoot = b.directory?.relative_path === ".";

    // Root always comes first
    if (aIsRoot && !bIsRoot) return -1;
    if (!aIsRoot && bIsRoot) return 1;

    // Otherwise alphabetical by display name
    return a.name.localeCompare(b.name, undefined, { sensitivity: 'base' });
  }

  function sortChildren(node: TreeNode): void {
    node.children.sort(sortNodes);
    node.children.forEach(sortChildren);
  }

  roots.sort(sortNodes);
  roots.forEach(sortChildren);

  return roots;
}

export function updateNodeExpansion(
  nodes: TreeNode[],
  targetPath: string,
  expanded: boolean
): TreeNode[] {
  return nodes.map((node) => {
    if (node.fullPath === targetPath) {
      return { ...node, isExpanded: expanded };
    }
    if (node.children.length > 0) {
      return {
        ...node,
        children: updateNodeExpansion(node.children, targetPath, expanded),
      };
    }
    return node;
  });
}
