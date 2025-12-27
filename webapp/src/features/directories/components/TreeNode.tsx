import { ChevronRight, ChevronDown, Folder, FolderOpen } from "lucide-react";
import { useMemo } from "react";
import type { TreeNode as TreeNodeType } from "../utils/treeUtils";

interface TreeNodeProps {
  node: TreeNodeType;
  selectedPath: string | null;
  onToggle: (path: string) => void;
  onSelect: (path: string) => void;
  unreadCounts?: Record<string, number>;
}

export function TreeNode({
  node,
  selectedPath,
  onToggle,
  onSelect,
  unreadCounts = {}
}: TreeNodeProps) {
  // When expanded, show only direct count (children show their own)
  // When collapsed, aggregate all descendant counts into one badge
  const unreadCount = useMemo(() => {
    const directCount = unreadCounts[node.fullPath] || 0;

    if (node.isExpanded) {
      return directCount;
    }

    // Collapsed: sum counts for all paths under this node
    let total = directCount;
    const prefix = node.fullPath + '/';
    for (const [path, count] of Object.entries(unreadCounts)) {
      if (path.startsWith(prefix)) {
        total += count;
      }
    }
    return total;
  }, [unreadCounts, node.fullPath, node.isExpanded]);

  const hasChildren = node.children.length > 0;
  const isAmplified = node.directory !== null;
  const isSelected = isAmplified && node.fullPath === selectedPath;
  const isIntermediate = !isAmplified && hasChildren;

  const handleChevronClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (hasChildren) {
      onToggle(node.fullPath);
    }
  };

  const handleLabelClick = () => {
    if (isAmplified) {
      onSelect(node.fullPath);
    }
  };

  return (
    <>
      <div
        className={`
          flex items-center gap-2 py-2 px-3 rounded-lg
          ${isIntermediate ? "text-gray-400" : ""}
          ${isAmplified ? "cursor-pointer hover:bg-gray-50" : ""}
          ${isSelected ? "bg-blue-50 text-blue-700" : ""}
        `}
        style={{ paddingLeft: `${node.depth * 20 + 12}px` }}
        onClick={handleLabelClick}
      >
        {/* Chevron for expandable nodes */}
        {hasChildren ? (
          <button
            onClick={handleChevronClick}
            className="p-0 hover:bg-gray-200 rounded"
            aria-label={node.isExpanded ? "Collapse" : "Expand"}
          >
            {node.isExpanded ? (
              <ChevronDown className="w-4 h-4" />
            ) : (
              <ChevronRight className="w-4 h-4" />
            )}
          </button>
        ) : (
          <span className="w-4" />
        )}

        {/* Folder icon */}
        {isAmplified ? (
          node.isExpanded ? (
            <FolderOpen className="w-4 h-4 text-blue-500" />
          ) : (
            <Folder className="w-4 h-4 text-blue-500" />
          )
        ) : (
          <Folder className="w-4 h-4 text-gray-400" />
        )}

        {/* Node name */}
        <span className={`flex-1 ${isIntermediate ? "font-normal" : "font-medium"}`}>
          {node.name}
        </span>

        {/* Unread badge */}
        {unreadCount > 0 && (
          <span
            className="ml-2 px-1.5 py-0.5 text-xs bg-blue-600 text-white rounded-full font-medium"
            title={`${unreadCount} unread session${unreadCount === 1 ? '' : 's'}`}
          >
            {unreadCount}
          </span>
        )}
      </div>

      {/* Render children if expanded */}
      {node.isExpanded &&
        node.children.map((child) => (
          <TreeNode
            key={child.fullPath}
            node={child}
            selectedPath={selectedPath}
            onToggle={onToggle}
            onSelect={onSelect}
            unreadCounts={unreadCounts}
          />
        ))}
    </>
  );
}
