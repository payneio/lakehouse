import type { ToolCall } from '../types/execution';

// Extract a short preview string for known tool types (shown on the collapsed row)
export function getToolPreview(tool: ToolCall): string | null {
  if (!tool.arguments) return null;
  switch (tool.name) {
    case 'bash':
      return tool.arguments.command ? String(tool.arguments.command) : null;
    case 'read_file':
      return tool.arguments.file_path ? String(tool.arguments.file_path) : null;
    case 'write_file':
    case 'edit_file':
      return tool.arguments.file_path ? String(tool.arguments.file_path) : null;
    case 'grep':
      return tool.arguments.pattern ? String(tool.arguments.pattern) : null;
    case 'glob':
      return tool.arguments.pattern ? String(tool.arguments.pattern) : null;
    case 'web_fetch':
      return tool.arguments.url ? String(tool.arguments.url) : null;
    case 'delegate':
      return tool.arguments.agent ? String(tool.arguments.agent) : null;
    default:
      return null;
  }
}
