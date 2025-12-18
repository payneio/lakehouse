/**
 * AutomationsSection - Real automation management with backend integration
 */
import { useState, useEffect } from "react";
import { formatDistanceToNow } from "date-fns";
import {
  CheckCircle,
  XCircle,
  Loader2,
  Trash2,
  Plus,
  Power,
  PowerOff,
  Clock,
  AlertCircle,
  Edit,
  Play,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useAutomations } from "@/hooks/useAutomations";
import type { Automation, ScheduleConfig } from "@/api/automations";
import { formatSchedule } from "@/api/automations";
import { generateTimeOfDayCron, parseTimeOfDayCron, type TimeOfDaySchedule } from "@/utils/cronUtils";

interface AutomationsSectionProps {
  projectId: string;
}

export function AutomationsSection({ projectId }: AutomationsSectionProps) {
  const {
    automations,
    isLoading,
    isError,
    error,
    create,
    update,
    delete: deleteOp,
    toggle,
    execute,
  } = useAutomations(projectId);

  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [automationToEdit, setAutomationToEdit] = useState<Automation | null>(
    null
  );
  const [automationToDelete, setAutomationToDelete] = useState<string | null>(
    null
  );

  const handleAddAutomation = async (automation: {
    name: string;
    message: string;
    schedule: ScheduleConfig;
  }) => {
    try {
      await create.mutateAsync({
        ...automation,
        enabled: true,
      });
      setIsAddDialogOpen(false);
    } catch (err) {
      console.error("Failed to create automation:", err);
    }
  };

  const handleEditAutomation = async (automation: {
    name: string;
    message: string;
    schedule: ScheduleConfig;
    enabled: boolean;
  }) => {
    if (!automationToEdit) return;

    try {
      await update.mutateAsync({
        id: automationToEdit.id,
        update: automation,
      });
      setIsEditDialogOpen(false);
      setAutomationToEdit(null);
    } catch (err) {
      console.error("Failed to update automation:", err);
    }
  };

  const handleDeleteAutomation = async (automationId: string) => {
    try {
      await deleteOp.mutateAsync(automationId);
      setAutomationToDelete(null);
    } catch (err) {
      console.error("Failed to delete automation:", err);
    }
  };

  const handleToggleAutomation = async (
    automationId: string,
    enabled: boolean
  ) => {
    try {
      await toggle.mutateAsync({ id: automationId, enabled });
    } catch (err) {
      console.error("Failed to toggle automation:", err);
    }
  };

  const handleExecuteAutomation = async (automationId: string) => {
    try {
      await execute.mutateAsync(automationId);
    } catch (err) {
      console.error("Failed to execute automation:", err);
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="flex justify-end">
          <div className="h-9 w-32 bg-muted animate-pulse rounded-md" />
        </div>
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="border rounded-lg p-4 space-y-3 animate-pulse"
            >
              <div className="h-6 w-48 bg-muted rounded" />
              <div className="h-4 w-full bg-muted rounded" />
              <div className="h-4 w-32 bg-muted rounded" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="border border-destructive rounded-lg p-4">
        <div className="flex items-center gap-2 text-destructive mb-2">
          <AlertCircle className="h-5 w-5" />
          <h4 className="font-semibold">Failed to load automations</h4>
        </div>
        <p className="text-sm text-muted-foreground">
          {error instanceof Error ? error.message : "An unknown error occurred"}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <button
          onClick={() => setIsAddDialogOpen(true)}
          className="flex items-center gap-2 px-3 py-2 border rounded-md hover:bg-accent text-sm"
        >
          <Plus className="h-4 w-4" />
          Add Automation
        </button>
      </div>

      {automations.length === 0 ? (
        <div className="border rounded-lg p-8 text-center text-muted-foreground">
          No automations configured. Add your first automation to get started.
        </div>
      ) : (
        <div className="space-y-4">
          {automations.map((automation) => (
            <AutomationCard
              key={automation.id}
              automation={automation}
              onToggle={handleToggleAutomation}
              onEdit={(automation) => {
                setAutomationToEdit(automation);
                setIsEditDialogOpen(true);
              }}
              onDelete={(id) => setAutomationToDelete(id)}
              onExecute={handleExecuteAutomation}
              isTogglingDisabled={toggle.isPending}
              isExecuting={execute.isPending && execute.variables === automation.id}
            />
          ))}
        </div>
      )}

      <AddAutomationDialog
        open={isAddDialogOpen}
        onOpenChange={setIsAddDialogOpen}
        onAdd={handleAddAutomation}
        isPending={create.isPending}
      />

      <EditAutomationDialog
        open={isEditDialogOpen}
        onOpenChange={setIsEditDialogOpen}
        onEdit={handleEditAutomation}
        automation={automationToEdit}
        isPending={update.isPending}
      />

      <Dialog
        open={automationToDelete !== null}
        onOpenChange={(open) => !open && setAutomationToDelete(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Automation</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete this automation? This action
              cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <button
              onClick={() => setAutomationToDelete(null)}
              className="px-3 py-2 border rounded-md hover:bg-accent text-sm"
              disabled={deleteOp.isPending}
            >
              Cancel
            </button>
            <button
              onClick={() =>
                automationToDelete && handleDeleteAutomation(automationToDelete)
              }
              disabled={deleteOp.isPending}
              className="px-3 py-2 bg-destructive text-destructive-foreground rounded-md hover:bg-destructive/90 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {deleteOp.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin inline mr-2" />
                  Deleting...
                </>
              ) : (
                "Delete"
              )}
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

interface AutomationCardProps {
  automation: Automation;
  onToggle: (id: string, enabled: boolean) => void;
  onEdit: (automation: Automation) => void;
  onDelete: (id: string) => void;
  onExecute: (id: string) => void;
  isTogglingDisabled: boolean;
  isExecuting: boolean;
}

function AutomationCard({
  automation,
  onToggle,
  onEdit,
  onDelete,
  onExecute,
  isTogglingDisabled,
  isExecuting,
}: AutomationCardProps) {
  const scheduleText = formatSchedule(automation.schedule);

  return (
    <div className="border rounded-lg p-4">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 mb-2">
            <h4 className="font-semibold truncate">{automation.name}</h4>
            <div
              className={`flex items-center gap-1 text-sm ${
                automation.enabled ? "text-green-600" : "text-gray-500"
              }`}
            >
              {automation.enabled ? (
                <>
                  <CheckCircle className="h-4 w-4" />
                  <span>Enabled</span>
                </>
              ) : (
                <>
                  <XCircle className="h-4 w-4" />
                  <span>Disabled</span>
                </>
              )}
            </div>
          </div>
          <p className="text-sm text-muted-foreground mb-3">
            {automation.message}
          </p>
          <div className="flex flex-col gap-2 text-xs text-muted-foreground">
            <div className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              <span className="font-medium">Schedule:</span> {scheduleText}
            </div>
            {automation.next_execution && automation.enabled && (
              <div>
                <span className="font-medium">Next run:</span>{" "}
                {formatDistanceToNow(new Date(automation.next_execution), {
                  addSuffix: true,
                })}
              </div>
            )}
            {automation.last_execution && (
              <div>
                <span className="font-medium">Last run:</span>{" "}
                {formatDistanceToNow(new Date(automation.last_execution), {
                  addSuffix: true,
                })}
              </div>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={() => onExecute(automation.id)}
            disabled={isExecuting}
            className="flex items-center gap-2 px-3 py-2 border rounded-md hover:bg-accent text-sm disabled:opacity-50 disabled:cursor-not-allowed"
            title="Run automation now"
          >
            {isExecuting ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Play className="h-4 w-4" />
            )}
            {isExecuting ? "Running..." : "Run Now"}
          </button>
          <button
            onClick={() => onToggle(automation.id, !automation.enabled)}
            disabled={isTogglingDisabled}
            className={`flex items-center gap-2 px-3 py-2 border rounded-md text-sm disabled:opacity-50 disabled:cursor-not-allowed ${
              automation.enabled
                ? "border-orange-600 text-orange-600 hover:bg-orange-50"
                : "border-green-600 text-green-600 hover:bg-green-50"
            }`}
            title={automation.enabled ? "Disable automation" : "Enable automation"}
          >
            {automation.enabled ? (
              <PowerOff className="h-4 w-4" />
            ) : (
              <Power className="h-4 w-4" />
            )}
            {automation.enabled ? "Disable" : "Enable"}
          </button>
          <button
            onClick={() => onEdit(automation)}
            className="flex items-center gap-2 px-3 py-2 border rounded-md hover:bg-accent text-sm"
            title="Edit automation"
          >
            <Edit className="h-4 w-4" />
          </button>
          <button
            onClick={() => onDelete(automation.id)}
            className="flex items-center gap-2 px-3 py-2 border border-destructive text-destructive rounded-md hover:bg-destructive/10 text-sm"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

interface AddAutomationDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onAdd: (automation: {
    name: string;
    message: string;
    schedule: ScheduleConfig;
  }) => void;
  isPending: boolean;
}

function AddAutomationDialog({
  open,
  onOpenChange,
  onAdd,
  isPending,
}: AddAutomationDialogProps) {
  const [name, setName] = useState("");
  const [message, setMessage] = useState("");
  const [scheduleType, setScheduleType] = useState<"preset" | "interval" | "timeOfDay">(
    "preset"
  );
  const [presetSchedule, setPresetSchedule] = useState("daily_9am");
  const [intervalValue, setIntervalValue] = useState("1");
  const [intervalUnit, setIntervalUnit] = useState<"m" | "h" | "d">("h");

  // Time-of-day state
  const [timeOfDayHour, setTimeOfDayHour] = useState("9");
  const [timeOfDayMinute, setTimeOfDayMinute] = useState("0");
  const [timeOfDayPeriod, setTimeOfDayPeriod] = useState<"AM" | "PM">("AM");
  const [timeOfDayFrequency, setTimeOfDayFrequency] = useState<"daily" | "weekdays" | "specific">("daily");
  const [timeOfDayDays, setTimeOfDayDays] = useState<number[]>([]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !message.trim()) return;

    let schedule: ScheduleConfig;

    if (scheduleType === "preset") {
      const presetMap: Record<string, ScheduleConfig> = {
        daily_9am: { type: "cron", value: "0 9 * * *" },
        weekly_monday: { type: "cron", value: "0 9 * * 1" },
        every_hour: { type: "interval", value: "1h" },
        every_30min: { type: "interval", value: "30m" },
      };
      schedule = presetMap[presetSchedule];
    } else if (scheduleType === "timeOfDay") {
      // Generate cron from time-of-day inputs
      const timeSchedule: TimeOfDaySchedule = {
        hour: parseInt(timeOfDayHour),
        minute: parseInt(timeOfDayMinute),
        period: timeOfDayPeriod,
        frequency: timeOfDayFrequency,
        days: timeOfDayFrequency === "specific" ? timeOfDayDays : undefined,
      };
      const cronExpr = generateTimeOfDayCron(timeSchedule);
      schedule = { type: "cron", value: cronExpr };
    } else {
      // Custom interval
      schedule = {
        type: "interval",
        value: `${intervalValue}${intervalUnit}`,
      };
    }

    onAdd({
      name: name.trim(),
      message: message.trim(),
      schedule,
    });

    // Reset form
    setName("");
    setMessage("");
    setScheduleType("preset");
    setPresetSchedule("daily_9am");
    setTimeOfDayHour("9");
    setTimeOfDayMinute("0");
    setTimeOfDayPeriod("AM");
    setTimeOfDayFrequency("daily");
    setTimeOfDayDays([]);
  };

  const handleCancel = () => {
    setName("");
    setMessage("");
    setScheduleType("preset");
    setPresetSchedule("daily_9am");
    setTimeOfDayHour("9");
    setTimeOfDayMinute("0");
    setTimeOfDayPeriod("AM");
    setTimeOfDayFrequency("daily");
    setTimeOfDayDays([]);
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Add Automation</DialogTitle>
          <DialogDescription>
            Create a new scheduled automation for this project
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="flex flex-col min-h-0 flex-1">
          <div className="space-y-4 py-4 overflow-y-auto flex-1">
            <div className="space-y-2">
              <label htmlFor="name" className="text-sm font-medium">
                Automation Name
              </label>
              <input
                id="name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full px-3 py-2 border rounded-md"
                placeholder="e.g., Daily Report Generator"
                required
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="message" className="text-sm font-medium">
                Prompt Message
              </label>
              <textarea
                id="message"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                className="w-full px-3 py-2 border rounded-md min-h-[100px] resize-y"
                placeholder="Enter the prompt that will be sent when this automation runs..."
                required
              />
              <p className="text-xs text-muted-foreground">
                This message will be sent to the AI agent when the automation
                runs
              </p>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Schedule Type</label>
              <div className="flex gap-4">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    value="preset"
                    checked={scheduleType === "preset"}
                    onChange={(e) =>
                      setScheduleType(e.target.value as "preset" | "interval" | "timeOfDay")
                    }
                  />
                  <span className="text-sm">Preset Schedules</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    value="interval"
                    checked={scheduleType === "interval"}
                    onChange={(e) =>
                      setScheduleType(e.target.value as "preset" | "interval" | "timeOfDay")
                    }
                  />
                  <span className="text-sm">Custom Interval</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    value="timeOfDay"
                    checked={scheduleType === "timeOfDay"}
                    onChange={(e) =>
                      setScheduleType(e.target.value as "preset" | "interval" | "timeOfDay")
                    }
                  />
                  <span className="text-sm">Specific Time</span>
                </label>
              </div>
            </div>

            {scheduleType === "preset" && (
              <div className="space-y-2">
                <label htmlFor="preset" className="text-sm font-medium">
                  Schedule
                </label>
                <select
                  id="preset"
                  value={presetSchedule}
                  onChange={(e) => setPresetSchedule(e.target.value)}
                  className="w-full px-3 py-2 border rounded-md"
                >
                  <option value="daily_9am">Daily at 9:00 AM</option>
                  <option value="weekly_monday">Weekly on Mondays at 9:00 AM</option>
                  <option value="every_hour">Every hour</option>
                  <option value="every_30min">Every 30 minutes</option>
                </select>
              </div>
            )}

            {scheduleType === "interval" && (
              <div className="space-y-2">
                <label className="text-sm font-medium">Interval</label>
                <div className="flex gap-2">
                  <input
                    type="number"
                    min="1"
                    value={intervalValue}
                    onChange={(e) => setIntervalValue(e.target.value)}
                    className="w-24 px-3 py-2 border rounded-md"
                  />
                  <select
                    value={intervalUnit}
                    onChange={(e) =>
                      setIntervalUnit(e.target.value as "m" | "h" | "d")
                    }
                    className="px-3 py-2 border rounded-md"
                  >
                    <option value="m">Minutes</option>
                    <option value="h">Hours</option>
                    <option value="d">Days</option>
                  </select>
                </div>
              </div>
            )}

            {scheduleType === "timeOfDay" && (
              <>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Time</label>
                  <div className="flex gap-2 items-center">
                    <select
                      value={timeOfDayHour}
                      onChange={(e) => setTimeOfDayHour(e.target.value)}
                      className="px-3 py-2 border rounded-md"
                    >
                      {Array.from({ length: 12 }, (_, i) => i + 1).map((h) => (
                        <option key={h} value={h}>
                          {h}
                        </option>
                      ))}
                    </select>
                    <span className="text-sm">:</span>
                    <select
                      value={timeOfDayMinute}
                      onChange={(e) => setTimeOfDayMinute(e.target.value)}
                      className="px-3 py-2 border rounded-md"
                    >
                      <option value="0">00</option>
                      <option value="15">15</option>
                      <option value="30">30</option>
                      <option value="45">45</option>
                    </select>
                    <select
                      value={timeOfDayPeriod}
                      onChange={(e) => setTimeOfDayPeriod(e.target.value as "AM" | "PM")}
                      className="px-3 py-2 border rounded-md"
                    >
                      <option value="AM">AM</option>
                      <option value="PM">PM</option>
                    </select>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    All times are in UTC timezone
                  </p>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Frequency</label>
                  <div className="space-y-2">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="radio"
                        value="daily"
                        checked={timeOfDayFrequency === "daily"}
                        onChange={(e) => setTimeOfDayFrequency(e.target.value as "daily" | "weekdays" | "specific")}
                      />
                      <span className="text-sm">Every day</span>
                    </label>
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="radio"
                        value="weekdays"
                        checked={timeOfDayFrequency === "weekdays"}
                        onChange={(e) => setTimeOfDayFrequency(e.target.value as "daily" | "weekdays" | "specific")}
                      />
                      <span className="text-sm">Weekdays (Mon-Fri)</span>
                    </label>
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="radio"
                        value="specific"
                        checked={timeOfDayFrequency === "specific"}
                        onChange={(e) => setTimeOfDayFrequency(e.target.value as "daily" | "weekdays" | "specific")}
                      />
                      <span className="text-sm">Specific days</span>
                    </label>
                    {timeOfDayFrequency === "specific" && (
                      <div className="flex flex-wrap gap-3 ml-6">
                        {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((day, index) => (
                          <label key={day} className="flex items-center gap-1 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={timeOfDayDays.includes(index)}
                              onChange={(e) => {
                                if (e.target.checked) {
                                  setTimeOfDayDays([...timeOfDayDays, index].sort());
                                } else {
                                  setTimeOfDayDays(timeOfDayDays.filter((d) => d !== index));
                                }
                              }}
                              className="rounded"
                            />
                            <span className="text-sm">{day}</span>
                          </label>
                        ))}
                      </div>
                    )}
                    {timeOfDayFrequency === "specific" && timeOfDayDays.length === 0 && (
                      <p className="text-xs text-destructive ml-6">
                        Please select at least one day
                      </p>
                    )}
                  </div>
                </div>
              </>
            )}
          </div>
          <DialogFooter>
            <button
              type="button"
              onClick={handleCancel}
              className="px-3 py-2 border rounded-md hover:bg-accent text-sm"
              disabled={isPending}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isPending || (scheduleType === "timeOfDay" && timeOfDayFrequency === "specific" && timeOfDayDays.length === 0)}
              className="px-3 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin inline mr-2" />
                  Creating...
                </>
              ) : (
                "Add Automation"
              )}
            </button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

interface EditAutomationDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onEdit: (automation: {
    name: string;
    message: string;
    schedule: ScheduleConfig;
    enabled: boolean;
  }) => void;
  automation: Automation | null;
  isPending: boolean;
}

function EditAutomationDialog({
  open,
  onOpenChange,
  onEdit,
  automation,
  isPending,
}: EditAutomationDialogProps) {
  // Initialize state from automation prop
  const getInitialState = () => {
    if (!automation) {
      return {
        name: "",
        message: "",
        enabled: true,
        scheduleType: "preset" as const,
        presetSchedule: "daily_9am",
        intervalValue: "1",
        intervalUnit: "h" as const,
        timeOfDayHour: "9",
        timeOfDayMinute: "0",
        timeOfDayPeriod: "AM" as const,
        timeOfDayFrequency: "daily" as const,
        timeOfDayDays: [] as number[],
      };
    }

    let scheduleType: "preset" | "interval" | "timeOfDay" = "preset";
    let presetSchedule = "daily_9am";
    let intervalValue = "1";
    let intervalUnit: "m" | "h" | "d" = "h";
    let timeOfDayHour = "9";
    let timeOfDayMinute = "0";
    let timeOfDayPeriod: "AM" | "PM" = "AM";
    let timeOfDayFrequency: "daily" | "weekdays" | "specific" = "daily";
    let timeOfDayDays: number[] = [];

    if (automation.schedule.type === "cron") {
      const cronToPreset: Record<string, string> = {
        "0 9 * * *": "daily_9am",
        "0 9 * * 1": "weekly_monday",
        "0 * * * *": "every_hour",
      };

      // Try parsing as time-of-day cron first
      const parsed = parseTimeOfDayCron(automation.schedule.value);
      if (parsed) {
        scheduleType = "timeOfDay";
        timeOfDayHour = parsed.hour.toString();
        timeOfDayMinute = parsed.minute.toString();
        timeOfDayPeriod = parsed.period;
        timeOfDayFrequency = parsed.frequency;
        timeOfDayDays = parsed.days || [];
      } else {
        // Fall back to preset matching
        presetSchedule = cronToPreset[automation.schedule.value] || "daily_9am";
      }
    } else if (automation.schedule.type === "interval") {
      const match = automation.schedule.value.match(/^(\d+)([mhd])$/);
      if (match) {
        const presetIntervals = ["1h", "30m"];
        if (presetIntervals.includes(automation.schedule.value)) {
          presetSchedule =
            automation.schedule.value === "1h" ? "every_hour" : "every_30min";
        } else {
          scheduleType = "interval";
          intervalValue = match[1];
          intervalUnit = match[2] as "m" | "h" | "d";
        }
      }
    }

    return {
      name: automation.name,
      message: automation.message,
      enabled: automation.enabled,
      scheduleType,
      presetSchedule,
      intervalValue,
      intervalUnit,
      timeOfDayHour,
      timeOfDayMinute,
      timeOfDayPeriod,
      timeOfDayFrequency,
      timeOfDayDays,
    };
  };

  const initialState = getInitialState();
  const [name, setName] = useState(initialState.name);
  const [message, setMessage] = useState(initialState.message);
  const [enabled, setEnabled] = useState(initialState.enabled);
  const [scheduleType, setScheduleType] = useState<"preset" | "interval" | "timeOfDay">(
    initialState.scheduleType
  );
  const [presetSchedule, setPresetSchedule] = useState(initialState.presetSchedule);
  const [intervalValue, setIntervalValue] = useState(initialState.intervalValue);
  const [intervalUnit, setIntervalUnit] = useState<"m" | "h" | "d">(
    initialState.intervalUnit
  );
  const [timeOfDayHour, setTimeOfDayHour] = useState(initialState.timeOfDayHour);
  const [timeOfDayMinute, setTimeOfDayMinute] = useState(initialState.timeOfDayMinute);
  const [timeOfDayPeriod, setTimeOfDayPeriod] = useState<"AM" | "PM">(initialState.timeOfDayPeriod);
  const [timeOfDayFrequency, setTimeOfDayFrequency] = useState<"daily" | "weekdays" | "specific">(initialState.timeOfDayFrequency);
  const [timeOfDayDays, setTimeOfDayDays] = useState<number[]>(initialState.timeOfDayDays);

  // Reset form when dialog opens with new automation
  useEffect(() => {
    if (open && automation) {
      const state = getInitialState();
      setName(state.name);
      setMessage(state.message);
      setEnabled(state.enabled);
      setScheduleType(state.scheduleType);
      setPresetSchedule(state.presetSchedule);
      setIntervalValue(state.intervalValue);
      setIntervalUnit(state.intervalUnit);
      setTimeOfDayHour(state.timeOfDayHour);
      setTimeOfDayMinute(state.timeOfDayMinute);
      setTimeOfDayPeriod(state.timeOfDayPeriod);
      setTimeOfDayFrequency(state.timeOfDayFrequency);
      setTimeOfDayDays(state.timeOfDayDays);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, automation?.id]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !message.trim()) return;

    let schedule: ScheduleConfig;

    if (scheduleType === "preset") {
      const presetMap: Record<string, ScheduleConfig> = {
        daily_9am: { type: "cron", value: "0 9 * * *" },
        weekly_monday: { type: "cron", value: "0 9 * * 1" },
        every_hour: { type: "interval", value: "1h" },
        every_30min: { type: "interval", value: "30m" },
      };
      schedule = presetMap[presetSchedule];
    } else if (scheduleType === "timeOfDay") {
      // Generate cron from time-of-day inputs
      const timeSchedule: TimeOfDaySchedule = {
        hour: parseInt(timeOfDayHour),
        minute: parseInt(timeOfDayMinute),
        period: timeOfDayPeriod,
        frequency: timeOfDayFrequency,
        days: timeOfDayFrequency === "specific" ? timeOfDayDays : undefined,
      };
      const cronExpr = generateTimeOfDayCron(timeSchedule);
      schedule = { type: "cron", value: cronExpr };
    } else {
      // Custom interval
      schedule = {
        type: "interval",
        value: `${intervalValue}${intervalUnit}`,
      };
    }

    onEdit({
      name: name.trim(),
      message: message.trim(),
      schedule,
      enabled,
    });
  };

  const handleCancel = () => {
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Edit Automation</DialogTitle>
          <DialogDescription>
            Update the automation settings
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="flex flex-col min-h-0 flex-1">
          <div className="space-y-4 py-4 overflow-y-auto flex-1">
            <div className="space-y-2">
              <label htmlFor="edit-name" className="text-sm font-medium">
                Automation Name
              </label>
              <input
                id="edit-name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full px-3 py-2 border rounded-md"
                placeholder="e.g., Daily Report Generator"
                required
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="edit-message" className="text-sm font-medium">
                Prompt Message
              </label>
              <textarea
                id="edit-message"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                className="w-full px-3 py-2 border rounded-md min-h-[100px] resize-y"
                placeholder="Enter the prompt that will be sent when this automation runs..."
                required
              />
              <p className="text-xs text-muted-foreground">
                This message will be sent to the AI agent when the automation
                runs
              </p>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Status</label>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="edit-enabled"
                  checked={enabled}
                  onChange={(e) => setEnabled(e.target.checked)}
                  className="rounded"
                />
                <label htmlFor="edit-enabled" className="text-sm cursor-pointer">
                  Enabled
                </label>
              </div>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Schedule Type</label>
              <div className="flex gap-4">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    value="preset"
                    checked={scheduleType === "preset"}
                    onChange={(e) =>
                      setScheduleType(e.target.value as "preset" | "interval" | "timeOfDay")
                    }
                  />
                  <span className="text-sm">Preset Schedules</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    value="interval"
                    checked={scheduleType === "interval"}
                    onChange={(e) =>
                      setScheduleType(e.target.value as "preset" | "interval" | "timeOfDay")
                    }
                  />
                  <span className="text-sm">Custom Interval</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    value="timeOfDay"
                    checked={scheduleType === "timeOfDay"}
                    onChange={(e) =>
                      setScheduleType(e.target.value as "preset" | "interval" | "timeOfDay")
                    }
                  />
                  <span className="text-sm">Specific Time</span>
                </label>
              </div>
            </div>

            {scheduleType === "preset" && (
              <div className="space-y-2">
                <label htmlFor="edit-preset" className="text-sm font-medium">
                  Schedule
                </label>
                <select
                  id="edit-preset"
                  value={presetSchedule}
                  onChange={(e) => setPresetSchedule(e.target.value)}
                  className="w-full px-3 py-2 border rounded-md"
                >
                  <option value="daily_9am">Daily at 9:00 AM</option>
                  <option value="weekly_monday">Weekly on Mondays at 9:00 AM</option>
                  <option value="every_hour">Every hour</option>
                  <option value="every_30min">Every 30 minutes</option>
                </select>
              </div>
            )}

            {scheduleType === "interval" && (
              <div className="space-y-2">
                <label className="text-sm font-medium">Interval</label>
                <div className="flex gap-2">
                  <input
                    type="number"
                    min="1"
                    value={intervalValue}
                    onChange={(e) => setIntervalValue(e.target.value)}
                    className="w-24 px-3 py-2 border rounded-md"
                  />
                  <select
                    value={intervalUnit}
                    onChange={(e) =>
                      setIntervalUnit(e.target.value as "m" | "h" | "d")
                    }
                    className="px-3 py-2 border rounded-md"
                  >
                    <option value="m">Minutes</option>
                    <option value="h">Hours</option>
                    <option value="d">Days</option>
                  </select>
                </div>
              </div>
            )}

            {scheduleType === "timeOfDay" && (
              <>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Time</label>
                  <div className="flex gap-2 items-center">
                    <select
                      value={timeOfDayHour}
                      onChange={(e) => setTimeOfDayHour(e.target.value)}
                      className="px-3 py-2 border rounded-md"
                    >
                      {Array.from({ length: 12 }, (_, i) => i + 1).map((h) => (
                        <option key={h} value={h}>
                          {h}
                        </option>
                      ))}
                    </select>
                    <span className="text-sm">:</span>
                    <select
                      value={timeOfDayMinute}
                      onChange={(e) => setTimeOfDayMinute(e.target.value)}
                      className="px-3 py-2 border rounded-md"
                    >
                      <option value="0">00</option>
                      <option value="15">15</option>
                      <option value="30">30</option>
                      <option value="45">45</option>
                    </select>
                    <select
                      value={timeOfDayPeriod}
                      onChange={(e) => setTimeOfDayPeriod(e.target.value as "AM" | "PM")}
                      className="px-3 py-2 border rounded-md"
                    >
                      <option value="AM">AM</option>
                      <option value="PM">PM</option>
                    </select>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    All times are in UTC timezone
                  </p>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Frequency</label>
                  <div className="space-y-2">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="radio"
                        value="daily"
                        checked={timeOfDayFrequency === "daily"}
                        onChange={(e) => setTimeOfDayFrequency(e.target.value as "daily" | "weekdays" | "specific")}
                      />
                      <span className="text-sm">Every day</span>
                    </label>
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="radio"
                        value="weekdays"
                        checked={timeOfDayFrequency === "weekdays"}
                        onChange={(e) => setTimeOfDayFrequency(e.target.value as "daily" | "weekdays" | "specific")}
                      />
                      <span className="text-sm">Weekdays (Mon-Fri)</span>
                    </label>
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="radio"
                        value="specific"
                        checked={timeOfDayFrequency === "specific"}
                        onChange={(e) => setTimeOfDayFrequency(e.target.value as "daily" | "weekdays" | "specific")}
                      />
                      <span className="text-sm">Specific days</span>
                    </label>
                    {timeOfDayFrequency === "specific" && (
                      <div className="flex flex-wrap gap-3 ml-6">
                        {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((day, index) => (
                          <label key={day} className="flex items-center gap-1 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={timeOfDayDays.includes(index)}
                              onChange={(e) => {
                                if (e.target.checked) {
                                  setTimeOfDayDays([...timeOfDayDays, index].sort());
                                } else {
                                  setTimeOfDayDays(timeOfDayDays.filter((d) => d !== index));
                                }
                              }}
                              className="rounded"
                            />
                            <span className="text-sm">{day}</span>
                          </label>
                        ))}
                      </div>
                    )}
                    {timeOfDayFrequency === "specific" && timeOfDayDays.length === 0 && (
                      <p className="text-xs text-destructive ml-6">
                        Please select at least one day
                      </p>
                    )}
                  </div>
                </div>
              </>
            )}
          </div>
          <DialogFooter>
            <button
              type="button"
              onClick={handleCancel}
              className="px-3 py-2 border rounded-md hover:bg-accent text-sm"
              disabled={isPending}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isPending || (scheduleType === "timeOfDay" && timeOfDayFrequency === "specific" && timeOfDayDays.length === 0)}
              className="px-3 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin inline mr-2" />
                  Updating...
                </>
              ) : (
                "Update Automation"
              )}
            </button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
