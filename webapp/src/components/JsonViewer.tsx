import { useState } from "react";
import { ChevronRight, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

interface JsonViewerProps {
  data: unknown;
  maxTextLength?: number;
  autoExpandFields?: string[];
  expandAllChildren?: string[];
  initialExpandDepth?: number;
}

type JsonValue =
  | string
  | number
  | boolean
  | null
  | undefined
  | JsonValue[]
  | { [key: string]: JsonValue };

export function JsonViewer({
  data,
  maxTextLength = 100,
  autoExpandFields = ["data", "content", "text", "request", "response"],
  expandAllChildren = ["messages", "content"],
  initialExpandDepth = 1,
}: JsonViewerProps) {
  return (
    <div className="font-mono text-sm">
      <JsonValue
        value={data as JsonValue}
        path=""
        depth={0}
        maxTextLength={maxTextLength}
        autoExpandFields={autoExpandFields}
        expandAllChildren={expandAllChildren}
        initialExpandDepth={initialExpandDepth}
      />
    </div>
  );
}

interface JsonValueProps {
  value: JsonValue;
  path: string;
  depth: number;
  maxTextLength: number;
  autoExpandFields: string[];
  expandAllChildren: string[];
  initialExpandDepth: number;
}

function JsonValue({
  value,
  path,
  depth,
  maxTextLength,
  autoExpandFields,
  expandAllChildren,
  initialExpandDepth,
}: JsonValueProps) {
  if (value === null) {
    return <span className="text-gray-500">null</span>;
  }

  if (value === undefined) {
    return <span className="text-gray-500">undefined</span>;
  }

  const type = typeof value;

  if (type === "boolean") {
    return <span className="text-purple-400">{value.toString()}</span>;
  }

  if (type === "number") {
    return <span className="text-cyan-400">{value.toString()}</span>;
  }

  if (type === "string") {
    return <JsonString value={value} maxTextLength={maxTextLength} />;
  }

  if (Array.isArray(value)) {
    return (
      <JsonArray
        value={value}
        path={path}
        depth={depth}
        maxTextLength={maxTextLength}
        autoExpandFields={autoExpandFields}
        expandAllChildren={expandAllChildren}
        initialExpandDepth={initialExpandDepth}
      />
    );
  }

  if (type === "object") {
    return (
      <JsonObject
        value={value as Record<string, JsonValue>}
        path={path}
        depth={depth}
        maxTextLength={maxTextLength}
        autoExpandFields={autoExpandFields}
        expandAllChildren={expandAllChildren}
        initialExpandDepth={initialExpandDepth}
      />
    );
  }

  return <span className="text-gray-400">{String(value)}</span>;
}

interface JsonStringProps {
  value: string;
  maxTextLength: number;
}

function JsonString({ value, maxTextLength }: JsonStringProps) {
  const [expanded, setExpanded] = useState(false);
  const isTruncated = value.length > maxTextLength;
  const hasNewlines = value.includes("\n");

  const displayValue = expanded ? value : value.substring(0, maxTextLength);

  return (
    <span
      className={cn(
        "text-green-400",
        isTruncated && "cursor-pointer hover:underline",
        hasNewlines && "whitespace-pre-wrap"
      )}
      onClick={isTruncated ? () => setExpanded(!expanded) : undefined}
      title={isTruncated && !expanded ? value : undefined}
    >
      "{displayValue}
      {isTruncated && !expanded && "..."}
      "
    </span>
  );
}

interface JsonArrayProps {
  value: JsonValue[];
  path: string;
  depth: number;
  maxTextLength: number;
  autoExpandFields: string[];
  expandAllChildren: string[];
  initialExpandDepth: number;
}

function JsonArray({
  value,
  path,
  depth,
  maxTextLength,
  autoExpandFields,
  expandAllChildren,
  initialExpandDepth,
}: JsonArrayProps) {
  const key = path.split(".").pop() || "";
  const shouldAutoExpand =
    depth === 0 ||
    depth < initialExpandDepth ||
    autoExpandFields.includes(key) ||
    expandAllChildren.some((field) => path.includes(field));

  const [expanded, setExpanded] = useState(shouldAutoExpand);

  if (value.length === 0) {
    return <span className="text-gray-500">[]</span>;
  }

  return (
    <span>
      <button
        onClick={() => setExpanded(!expanded)}
        className="inline-flex items-center text-gray-500 hover:text-gray-300"
      >
        {expanded ? (
          <ChevronDown className="h-3 w-3" />
        ) : (
          <ChevronRight className="h-3 w-3" />
        )}
      </button>
      <span className="text-gray-500">[</span>
      {!expanded && (
        <span className="text-gray-500 mx-1">
          {value.length} {value.length === 1 ? "item" : "items"}
        </span>
      )}
      {expanded && (
        <div className="ml-4 border-l border-gray-700 pl-2">
          {value.map((item, index) => (
            <div key={index} className="py-0.5">
              <JsonValue
                value={item}
                path={`${path}[${index}]`}
                depth={depth + 1}
                maxTextLength={maxTextLength}
                autoExpandFields={autoExpandFields}
                expandAllChildren={expandAllChildren}
                initialExpandDepth={initialExpandDepth}
              />
              {index < value.length - 1 && (
                <span className="text-gray-500">,</span>
              )}
            </div>
          ))}
        </div>
      )}
      <span className="text-gray-500">]</span>
    </span>
  );
}

interface JsonObjectProps {
  value: Record<string, JsonValue>;
  path: string;
  depth: number;
  maxTextLength: number;
  autoExpandFields: string[];
  expandAllChildren: string[];
  initialExpandDepth: number;
}

function JsonObject({
  value,
  path,
  depth,
  maxTextLength,
  autoExpandFields,
  expandAllChildren,
  initialExpandDepth,
}: JsonObjectProps) {
  const keys = Object.keys(value);
  const key = path.split(".").pop() || "";
  const shouldAutoExpand =
    depth === 0 ||
    depth < initialExpandDepth ||
    autoExpandFields.includes(key) ||
    expandAllChildren.some((field) => path.includes(field));

  const [expanded, setExpanded] = useState(shouldAutoExpand);

  if (keys.length === 0) {
    return <span className="text-gray-500">{"{}"}</span>;
  }

  return (
    <span>
      <button
        onClick={() => setExpanded(!expanded)}
        className="inline-flex items-center text-gray-500 hover:text-gray-300"
      >
        {expanded ? (
          <ChevronDown className="h-3 w-3" />
        ) : (
          <ChevronRight className="h-3 w-3" />
        )}
      </button>
      <span className="text-gray-500">{"{"}</span>
      {!expanded && <span className="text-gray-500 mx-1">...</span>}
      {expanded && (
        <div className="ml-4 border-l border-gray-700 pl-2">
          {keys.map((k, index) => (
            <div key={k} className="py-0.5">
              <span className="text-blue-400">"{k}"</span>
              <span className="text-gray-500">: </span>
              <JsonValue
                value={value[k]}
                path={path ? `${path}.${k}` : k}
                depth={depth + 1}
                maxTextLength={maxTextLength}
                autoExpandFields={autoExpandFields}
                expandAllChildren={expandAllChildren}
                initialExpandDepth={initialExpandDepth}
              />
              {index < keys.length - 1 && (
                <span className="text-gray-500">,</span>
              )}
            </div>
          ))}
        </div>
      )}
      <span className="text-gray-500">{"}"}</span>
    </span>
  );
}
