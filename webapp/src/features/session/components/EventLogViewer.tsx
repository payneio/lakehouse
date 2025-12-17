import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, X, RefreshCw } from "lucide-react";
import { getSessionEvents, type SessionEvent } from "@/api/sessions";
import { JsonViewer } from "@/components/JsonViewer";
import { cn } from "@/lib/utils";

interface EventLogViewerProps {
  sessionId: string;
}

// Log level colors (GitHub dark theme inspired)
const LEVEL_COLORS: Record<string, { bg: string; text: string }> = {
  INFO: { bg: "bg-blue-500/20", text: "text-blue-400" },
  DEBUG: { bg: "bg-cyan-500/20", text: "text-cyan-400" },
  WARNING: { bg: "bg-amber-500/20", text: "text-amber-400" },
  ERROR: { bg: "bg-red-500/20", text: "text-red-400" },
};

export function EventLogViewer({ sessionId }: EventLogViewerProps) {
  const [searchText, setSearchText] = useState("");
  const [levelFilter, setLevelFilter] = useState<string>("");
  const [eventTypeFilter, setEventTypeFilter] = useState<string>("");
  const [selectedEvent, setSelectedEvent] = useState<SessionEvent | null>(null);

  // Fetch events
  const {
    data,
    isLoading,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ["sessionEvents", sessionId],
    queryFn: () => getSessionEvents(sessionId, { limit: 1000 }),
    enabled: !!sessionId,
  });

  const events = data?.events || [];

  // Extract unique event types for filter dropdown
  const eventTypes = useMemo(() => {
    const types = new Set<string>();
    const prefixes = new Set<string>();

    events.forEach((e) => {
      if (e.event) {
        types.add(e.event);
        const prefix = e.event.split(":")[0];
        if (prefix) prefixes.add(prefix);
      }
    });

    // Group by prefix
    const grouped: { label: string; value: string }[] = [];
    Array.from(prefixes)
      .sort()
      .forEach((prefix) => {
        const prefixTypes = Array.from(types).filter((t) =>
          t.startsWith(prefix + ":")
        );
        if (prefixTypes.length > 1) {
          grouped.push({ label: `All ${prefix} events`, value: `${prefix}:` });
        }
        prefixTypes.sort().forEach((t) => {
          grouped.push({ label: t, value: t });
        });
      });

    return grouped;
  }, [events]);

  // Filter events
  const filteredEvents = useMemo(() => {
    return events.filter((event) => {
      // Level filter
      if (levelFilter && event.lvl?.toUpperCase() !== levelFilter) {
        return false;
      }

      // Event type filter (supports prefix matching)
      if (eventTypeFilter) {
        if (eventTypeFilter.endsWith(":")) {
          // Prefix match
          if (!event.event?.startsWith(eventTypeFilter)) {
            return false;
          }
        } else {
          // Exact match
          if (event.event !== eventTypeFilter) {
            return false;
          }
        }
      }

      // Text search (searches in JSON stringified event)
      if (searchText) {
        const searchLower = searchText.toLowerCase();
        const eventStr = JSON.stringify(event).toLowerCase();
        if (!eventStr.includes(searchLower)) {
          return false;
        }
      }

      return true;
    });
  }, [events, levelFilter, eventTypeFilter, searchText]);

  // Get smart preview text for an event
  const getEventPreview = (event: SessionEvent): string => {
    const eventType = event.event || "";
    const data = event.data as Record<string, unknown> | undefined;

    if (!data) return "";

    // Tool events
    if (eventType.startsWith("tool:")) {
      const toolName = data.tool_name || data.name;
      if (toolName) return String(toolName);
    }

    // LLM events
    if (eventType.startsWith("llm:")) {
      const model = data.model;
      if (model) return String(model);
    }

    // Prompt events
    if (eventType === "prompt:submit") {
      const prompt = data.prompt;
      if (typeof prompt === "string") {
        return prompt.length > 50 ? prompt.substring(0, 50) + "..." : prompt;
      }
    }

    // Thinking events
    if (eventType === "thinking:delta") {
      const delta = data.delta;
      if (typeof delta === "string") {
        return delta.length > 50 ? delta.substring(0, 50) + "..." : delta;
      }
    }

    return "";
  };

  const clearFilters = () => {
    setSearchText("");
    setLevelFilter("");
    setEventTypeFilter("");
  };

  const hasFilters = searchText || levelFilter || eventTypeFilter;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground">
        Loading events...
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full text-red-400">
        Failed to load events
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-gray-900">
      {/* Filter Bar */}
      <div className="flex items-center gap-2 p-2 border-b border-gray-700 bg-gray-800">
        {/* Search */}
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-500" />
          <input
            type="text"
            placeholder="Filter events..."
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 text-sm bg-gray-900 border border-gray-700 rounded focus:outline-none focus:border-blue-500 text-gray-200"
          />
        </div>

        {/* Level filter */}
        <select
          value={levelFilter}
          onChange={(e) => setLevelFilter(e.target.value)}
          className="px-2 py-1.5 text-sm bg-gray-900 border border-gray-700 rounded focus:outline-none focus:border-blue-500 text-gray-200"
        >
          <option value="">All Levels</option>
          <option value="INFO">INFO</option>
          <option value="DEBUG">DEBUG</option>
          <option value="WARNING">WARNING</option>
          <option value="ERROR">ERROR</option>
        </select>

        {/* Event type filter */}
        <select
          value={eventTypeFilter}
          onChange={(e) => setEventTypeFilter(e.target.value)}
          className="px-2 py-1.5 text-sm bg-gray-900 border border-gray-700 rounded focus:outline-none focus:border-blue-500 text-gray-200"
        >
          <option value="">All Event Types</option>
          {eventTypes.map((type) => (
            <option key={type.value} value={type.value}>
              {type.label}
            </option>
          ))}
        </select>

        {/* Clear filters */}
        {hasFilters && (
          <button
            onClick={clearFilters}
            className="px-2 py-1.5 text-sm text-gray-400 hover:text-gray-200"
          >
            Clear
          </button>
        )}

        {/* Refresh */}
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="p-1.5 text-gray-400 hover:text-gray-200 disabled:opacity-50"
          title="Refresh events"
        >
          <RefreshCw className={cn("h-4 w-4", isFetching && "animate-spin")} />
        </button>

        {/* Count */}
        <span className="text-xs text-gray-500">
          {filteredEvents.length} / {events.length} events
        </span>
      </div>

      {/* Two-pane layout */}
      <div className="flex flex-1 min-h-0">
        {/* Event List */}
        <div className="w-80 flex-shrink-0 border-r border-gray-700 overflow-y-auto">
          {filteredEvents.length === 0 ? (
            <div className="p-4 text-center text-gray-500">
              {events.length === 0 ? "No events" : "No matching events"}
            </div>
          ) : (
            filteredEvents.map((event, index) => {
              const level = (event.lvl || "INFO").toUpperCase();
              const levelColor = LEVEL_COLORS[level] || LEVEL_COLORS.INFO;
              const isSelected = selectedEvent === event;
              const preview = getEventPreview(event);

              return (
                <div
                  key={index}
                  onClick={() => setSelectedEvent(event)}
                  className={cn(
                    "px-3 py-2 border-b border-gray-800 cursor-pointer hover:bg-gray-800",
                    isSelected && "bg-blue-900/30"
                  )}
                >
                  <div className="flex items-center gap-2">
                    {/* Level badge */}
                    <span
                      className={cn(
                        "px-1.5 py-0.5 text-xs font-medium rounded",
                        levelColor.bg,
                        levelColor.text
                      )}
                    >
                      {level}
                    </span>
                    {/* Event type */}
                    <span className="text-sm text-gray-200 truncate flex-1">
                      {event.event}
                    </span>
                  </div>
                  {/* Timestamp */}
                  <div className="text-xs text-gray-500 mt-1">
                    {formatTimestamp(event.ts)}
                  </div>
                  {/* Preview */}
                  {preview && (
                    <div className="text-xs text-gray-400 mt-1 truncate">
                      {preview}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>

        {/* Detail Panel */}
        <div className="flex-1 overflow-y-auto bg-gray-900">
          {selectedEvent ? (
            <EventDetail event={selectedEvent} onClose={() => setSelectedEvent(null)} />
          ) : (
            <div className="flex items-center justify-center h-full text-gray-500">
              Select an event to view details
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

interface EventDetailProps {
  event: SessionEvent;
  onClose: () => void;
}

function EventDetail({ event, onClose }: EventDetailProps) {
  const [activeTab, setActiveTab] = useState<"overview" | "data" | "raw">(
    "overview"
  );

  const level = (event.lvl || "INFO").toUpperCase();
  const levelColor = LEVEL_COLORS[level] || LEVEL_COLORS.INFO;

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-gray-700 bg-gray-800">
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "px-1.5 py-0.5 text-xs font-medium rounded",
              levelColor.bg,
              levelColor.text
            )}
          >
            {level}
          </span>
          <span className="text-sm font-medium text-gray-200">
            {event.event}
          </span>
        </div>
        <button
          onClick={onClose}
          className="p-1 text-gray-400 hover:text-gray-200"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-gray-700 bg-gray-800">
        {(["overview", "data", "raw"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={cn(
              "px-4 py-2 text-sm font-medium capitalize",
              activeTab === tab
                ? "text-blue-400 border-b-2 border-blue-400"
                : "text-gray-400 hover:text-gray-200"
            )}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {activeTab === "overview" && (
          <div className="space-y-3">
            <DetailRow label="Event Type" value={event.event} />
            <DetailRow label="Level" value={level} />
            <DetailRow label="Timestamp" value={formatTimestamp(event.ts)} />
            {event.session_id && (
              <DetailRow label="Session ID" value={event.session_id} />
            )}
          </div>
        )}

        {activeTab === "data" && (
          <div>
            {event.data ? (
              <JsonViewer
                data={event.data}
                autoExpandFields={[
                  "data",
                  "content",
                  "text",
                  "request",
                  "response",
                  "tool_input",
                  "result",
                ]}
                expandAllChildren={["messages", "content"]}
                initialExpandDepth={2}
              />
            ) : (
              <span className="text-gray-500">No data</span>
            )}
          </div>
        )}

        {activeTab === "raw" && (
          <pre className="text-xs text-gray-300 whitespace-pre-wrap font-mono bg-gray-950 p-3 rounded overflow-x-auto">
            {JSON.stringify(event, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2">
      <span className="text-gray-500 w-24 flex-shrink-0">{label}:</span>
      <span className="text-gray-200 font-mono text-sm">{value}</span>
    </div>
  );
}

function formatTimestamp(ts: string): string {
  try {
    const date = new Date(ts);
    return date.toLocaleString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      fractionalSecondDigits: 3,
    });
  } catch {
    return ts;
  }
}
