import { useState, useEffect, useRef } from 'react';
import { Loader2, CheckCircle, XCircle, ChevronDown, ChevronUp } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

interface LogEntry {
  timestamp: string;
  level: 'info' | 'error' | 'warning';
  message: string;
}

interface WorkTask {
  id: string;
  name: string;
  status: 'running' | 'completed' | 'failed';
  created_at: string;
  completed_at?: string;
  progress?: number;
  logs: LogEntry[];
}

interface WorkSectionProps {
  directoryPath: string;
}

const LOG_COLORS = {
  info: 'text-gray-100',
  warning: 'text-yellow-400',
  error: 'text-red-400',
};

const STATUS_ICONS = {
  running: Loader2,
  completed: CheckCircle,
  failed: XCircle,
};

const STATUS_COLORS = {
  running: 'text-blue-600',
  completed: 'text-green-600',
  failed: 'text-red-600',
};

function formatLogTimestamp(timestamp: string): string {
  const date = new Date(timestamp);
  return date.toLocaleTimeString('en-US', { hour12: false });
}

function LogPanel({ task }: { task: WorkTask }) {
  const logContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (task.status === 'running' && logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [task.logs, task.status]);

  return (
    <div ref={logContainerRef} className="mt-3 bg-gray-900 text-gray-100 rounded-lg p-3 font-mono text-xs h-48 overflow-y-auto">
      {task.logs.map((log, index) => (
        <div key={index} className={LOG_COLORS[log.level]}>
          [{formatLogTimestamp(log.timestamp)}] {log.level.toUpperCase()}: {log.message}
        </div>
      ))}
    </div>
  );
}

function TaskCard({ task, isLogOpen, onToggleLogs }: {
  task: WorkTask;
  isLogOpen: boolean;
  onToggleLogs: () => void;
}) {
  const Icon = STATUS_ICONS[task.status];
  const isRunning = task.status === 'running';

  return (
    <div className="border rounded-lg p-4 bg-white">
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-3 flex-1">
          <Icon
            className={`${STATUS_COLORS[task.status]} ${isRunning ? 'animate-spin' : ''}`}
            size={20}
          />
          <div className="flex-1">
            <h4 className="font-medium text-gray-900">{task.name}</h4>
            <div className="text-sm text-gray-600 mt-1">
              {isRunning ? (
                <>Started {formatDistanceToNow(new Date(task.created_at), { addSuffix: true })}</>
              ) : task.status === 'completed' && task.completed_at ? (
                <>
                  Completed {formatDistanceToNow(new Date(task.completed_at), { addSuffix: true })}
                  {' • '}
                  Duration: {Math.round((new Date(task.completed_at).getTime() - new Date(task.created_at).getTime()) / 60000)} min
                </>
              ) : task.status === 'failed' && task.completed_at ? (
                <>Failed {formatDistanceToNow(new Date(task.completed_at), { addSuffix: true })}</>
              ) : null}
            </div>

            {isRunning && task.progress !== undefined && (
              <div className="mt-3">
                <div className="flex items-center justify-between text-sm mb-1">
                  <span className="text-gray-600">Progress</span>
                  <span className="text-gray-900 font-medium">{task.progress}%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-gradient-to-r from-blue-500 to-blue-600 h-2 rounded-full transition-all duration-300"
                    style={{ width: `${task.progress}%` }}
                  />
                </div>
              </div>
            )}
          </div>
        </div>

        <button
          onClick={onToggleLogs}
          className="ml-4 px-3 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors flex items-center gap-2"
        >
          {isLogOpen ? (
            <>
              Hide Logs <ChevronUp size={16} />
            </>
          ) : (
            <>
              View Logs <ChevronDown size={16} />
            </>
          )}
        </button>
      </div>

      {isLogOpen && <LogPanel task={task} />}
    </div>
  );
}

function TaskList({ title, tasks, openLogTaskId, onToggleLogs }: {
  title: string;
  tasks: WorkTask[];
  openLogTaskId: string | null;
  onToggleLogs: (taskId: string) => void;
}) {
  if (tasks.length === 0) {
    return null;
  }

  return (
    <div className="mb-6 last:mb-0">
      <h3 className="text-sm font-semibold text-gray-700 mb-3">
        {title} ({tasks.length})
      </h3>
      <div className="space-y-3">
        {tasks.map((task) => (
          <TaskCard
            key={task.id}
            task={task}
            isLogOpen={openLogTaskId === task.id}
            onToggleLogs={() => onToggleLogs(task.id)}
          />
        ))}
      </div>
    </div>
  );
}

function createMockTasks(): WorkTask[] {
  const now = Date.now();

  return [
    {
      id: '1',
      name: 'Generate Report',
      status: 'running',
      created_at: new Date(now - 2 * 60 * 1000).toISOString(),
      progress: 65,
      logs: [
        { timestamp: new Date(now - 2 * 60 * 1000).toISOString(), level: 'info', message: 'Starting report generation...' },
        { timestamp: new Date(now - 90 * 1000).toISOString(), level: 'info', message: 'Loading data sources...' },
        { timestamp: new Date(now - 60 * 1000).toISOString(), level: 'info', message: 'Processing 1,234 records...' },
        { timestamp: new Date(now - 30 * 1000).toISOString(), level: 'info', message: 'Generating charts and visualizations...' },
      ],
    },
    {
      id: '2',
      name: 'Sync Calendar',
      status: 'running',
      created_at: new Date(now - 5 * 60 * 1000).toISOString(),
      progress: 30,
      logs: [
        { timestamp: new Date(now - 5 * 60 * 1000).toISOString(), level: 'info', message: 'Connecting to calendar service...' },
        { timestamp: new Date(now - 4 * 60 * 1000).toISOString(), level: 'info', message: 'Fetching events from last 30 days...' },
        { timestamp: new Date(now - 3 * 60 * 1000).toISOString(), level: 'warning', message: 'Rate limit encountered, retrying...' },
        { timestamp: new Date(now - 2 * 60 * 1000).toISOString(), level: 'info', message: 'Synchronizing 47 events...' },
      ],
    },
    {
      id: '3',
      name: 'Email Analysis',
      status: 'completed',
      created_at: new Date(now - 12 * 60 * 1000).toISOString(),
      completed_at: new Date(now - 10 * 60 * 1000).toISOString(),
      logs: [
        { timestamp: new Date(now - 12 * 60 * 1000).toISOString(), level: 'info', message: 'Starting email analysis...' },
        { timestamp: new Date(now - 11 * 60 * 1000).toISOString(), level: 'info', message: 'Analyzing 156 unread emails...' },
        { timestamp: new Date(now - 10 * 60 * 1000).toISOString(), level: 'info', message: 'Analysis complete: 23 urgent, 89 normal, 44 low priority' },
      ],
    },
    {
      id: '4',
      name: 'Data Import',
      status: 'failed',
      created_at: new Date(now - 62 * 60 * 1000).toISOString(),
      completed_at: new Date(now - 60 * 60 * 1000).toISOString(),
      logs: [
        { timestamp: new Date(now - 62 * 60 * 1000).toISOString(), level: 'info', message: 'Starting data import from CSV...' },
        { timestamp: new Date(now - 61 * 60 * 1000).toISOString(), level: 'warning', message: 'Invalid data format in row 1,234' },
        { timestamp: new Date(now - 60 * 60 * 1000).toISOString(), level: 'error', message: 'Import failed: Too many validation errors' },
      ],
    },
    {
      id: '5',
      name: 'Backup Database',
      status: 'completed',
      created_at: new Date(now - 125 * 60 * 1000).toISOString(),
      completed_at: new Date(now - 120 * 60 * 1000).toISOString(),
      logs: [
        { timestamp: new Date(now - 125 * 60 * 1000).toISOString(), level: 'info', message: 'Starting database backup...' },
        { timestamp: new Date(now - 122 * 60 * 1000).toISOString(), level: 'info', message: 'Backing up 2.3 GB of data...' },
        { timestamp: new Date(now - 120 * 60 * 1000).toISOString(), level: 'info', message: 'Backup completed successfully' },
      ],
    },
    {
      id: '6',
      name: 'Process Images',
      status: 'completed',
      created_at: new Date(now - 185 * 60 * 1000).toISOString(),
      completed_at: new Date(now - 180 * 60 * 1000).toISOString(),
      logs: [
        { timestamp: new Date(now - 185 * 60 * 1000).toISOString(), level: 'info', message: 'Processing 48 images...' },
        { timestamp: new Date(now - 182 * 60 * 1000).toISOString(), level: 'info', message: 'Resizing and optimizing...' },
        { timestamp: new Date(now - 180 * 60 * 1000).toISOString(), level: 'info', message: 'All images processed' },
      ],
    },
    {
      id: '7',
      name: 'Generate Invoices',
      status: 'completed',
      created_at: new Date(now - 245 * 60 * 1000).toISOString(),
      completed_at: new Date(now - 240 * 60 * 1000).toISOString(),
      logs: [
        { timestamp: new Date(now - 245 * 60 * 1000).toISOString(), level: 'info', message: 'Generating monthly invoices...' },
        { timestamp: new Date(now - 242 * 60 * 1000).toISOString(), level: 'info', message: 'Created 34 invoices' },
        { timestamp: new Date(now - 240 * 60 * 1000).toISOString(), level: 'info', message: 'Invoices sent via email' },
      ],
    },
  ];
}

export function WorkSection({
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  directoryPath: _directoryPath, // Reserved for backend integration
}: WorkSectionProps) {
  const [tasks, setTasks] = useState<WorkTask[]>(createMockTasks());
  const [openLogTaskId, setOpenLogTaskId] = useState<string | null>(null);

  useEffect(() => {
    const interval = setInterval(() => {
      setTasks((prevTasks) => {
        const now = Date.now();
        return prevTasks.map((task) => {
          if (task.status !== 'running') {
            return task;
          }

          const newProgress = Math.min((task.progress || 0) + 5, 100);
          const newLog: LogEntry = {
            timestamp: new Date(now).toISOString(),
            level: 'info',
            message: `Processing... ${newProgress}% complete`,
          };

          if (newProgress >= 100) {
            return {
              ...task,
              status: 'completed' as const,
              progress: 100,
              completed_at: new Date(now).toISOString(),
              logs: [...task.logs, newLog, {
                timestamp: new Date(now).toISOString(),
                level: 'info',
                message: 'Task completed successfully',
              }],
            };
          }

          return {
            ...task,
            progress: newProgress,
            logs: [...task.logs, newLog],
          };
        });
      });
    }, 2000);

    return () => clearInterval(interval);
  }, []);

  const handleToggleLogs = (taskId: string) => {
    setOpenLogTaskId((prev) => (prev === taskId ? null : taskId));
  };

  const runningTasks = tasks.filter((t) => t.status === 'running');
  const completedTasks = tasks.filter((t) => t.status !== 'running');

  return (
    <div className="space-y-6">
      <TaskList
        title="Running Tasks"
        tasks={runningTasks}
        openLogTaskId={openLogTaskId}
        onToggleLogs={handleToggleLogs}
      />

      <TaskList
        title="Completed Tasks"
        tasks={completedTasks}
        openLogTaskId={openLogTaskId}
        onToggleLogs={handleToggleLogs}
      />
    </div>
  );
}
