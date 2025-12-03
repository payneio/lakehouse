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

  // Create all nodes first
  for (const dir of directories) {
    const segments = dir.relative_path.split("/");

    for (let i = 0; i < segments.length; i++) {
      const path = segments.slice(0, i + 1).join("/");

      if (!nodeMap.has(path)) {
        nodeMap.set(path, {
          name: segments[i],
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

  // Sort children by display name (metadata.name or path segment)
  function sortChildren(node: TreeNode): void {
    node.children.sort((a, b) => {
      const aName = (a.directory?.metadata?.name as string) || a.name;
      const bName = (b.directory?.metadata?.name as string) || b.name;
      return aName.localeCompare(bName, undefined, { sensitivity: 'base' });
    });
    node.children.forEach(sortChildren);
  }
  roots.sort((a, b) => {
    const aName = (a.directory?.metadata?.name as string) || a.name;
    const bName = (b.directory?.metadata?.name as string) || b.name;
    return aName.localeCompare(bName, undefined, { sensitivity: 'base' });
  });
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
