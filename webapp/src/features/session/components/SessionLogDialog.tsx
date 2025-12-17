import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { EventLogViewer } from "./EventLogViewer";

interface SessionLogDialogProps {
  sessionId: string;
  open: boolean;
  onClose: () => void;
}

export function SessionLogDialog({
  sessionId,
  open,
  onClose,
}: SessionLogDialogProps) {
  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DialogContent
        className="max-w-6xl h-[80vh] flex flex-col p-0 gap-0 bg-gray-900 border-gray-700"
        showCloseButton={false}
      >
        <DialogHeader className="px-4 py-3 border-b border-gray-700 flex-shrink-0">
          <DialogTitle className="text-gray-200">Session Events</DialogTitle>
        </DialogHeader>
        <div className="flex-1 min-h-0">
          <EventLogViewer sessionId={sessionId} />
        </div>
      </DialogContent>
    </Dialog>
  );
}
