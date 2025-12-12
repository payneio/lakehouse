"""Automation storage and lifecycle management."""

import json
import logging
import uuid
from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import Literal

from amplifier_library.models.automations import Automation
from amplifier_library.models.automations import AutomationIndex
from amplifier_library.models.automations import AutomationIndexEntry
from amplifier_library.models.automations import ExecutionRecord
from amplifier_library.models.automations import ScheduleConfig

logger = logging.getLogger(__name__)


class AutomationManager:
    """Manages automation lifecycle and persistence.

    Handles automation storage, indexing, and execution history tracking.
    Uses atomic file operations for reliability.

    Storage structure:
        state/automations/
            index.json                    # Fast lookup index
            {automation_id}.json          # Individual automation files
            executions/
                {automation_id}.jsonl     # Execution history (append-only)
    """

    def __init__(self, storage_dir: Path) -> None:
        """Initialize with storage directory.

        Args:
            storage_dir: Path to state directory (e.g., .amplifierd/state)
        """
        self.storage_dir = Path(storage_dir) / "automations"
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.executions_dir = self.storage_dir / "executions"
        self.executions_dir.mkdir(parents=True, exist_ok=True)

        self.index_path = self.storage_dir / "index.json"

    # --- Automation Management ---

    def create_automation(
        self,
        project_id: str,
        name: str,
        message: str,
        schedule: ScheduleConfig,
        enabled: bool = True,
    ) -> Automation:
        """Create new automation.

        Args:
            project_id: Path to amplified directory
            name: Human-readable automation name
            message: Message to send to agent on execution
            schedule: Schedule configuration
            enabled: Whether automation is active (default: True)

        Returns:
            Created Automation

        Raises:
            ValueError: If automation name already exists for project
            ValueError: If schedule configuration is invalid

        Side Effects:
            Creates automation file: state/automations/{automation_id}.json
            Updates index: state/automations/index.json
        """
        # Note: We don't validate project directory existence here because:
        # 1. project_id is a relative path from data_dir, not a filesystem path
        # 2. Automations can be created before directories are fully set up
        # 3. Validation happens naturally during execution when creating sessions
        # 4. Keeps the manager simple and focused on automation storage

        # Check for duplicate name within project
        existing = self.list_automations(project_id=project_id)
        if any(auto.name == name for auto in existing):
            raise ValueError(f"Automation with name '{name}' already exists for project {project_id}")

        # Create automation
        now = datetime.now(UTC)
        automation_id = str(uuid.uuid4())

        automation = Automation(
            id=automation_id,
            project_id=project_id,
            name=name,
            message=message,
            schedule=schedule,
            enabled=enabled,
            created_at=now,
            updated_at=now,
            last_execution=None,
            next_execution=None,  # Scheduler will calculate this
        )

        # Write automation file atomically
        automation_path = self.storage_dir / f"{automation_id}.json"
        tmp_path = automation_path.with_suffix(".tmp")
        tmp_path.write_text(automation.model_dump_json(indent=2))
        tmp_path.rename(automation_path)

        # Update index
        self._update_index(automation)

        logger.info(f"Created automation {automation_id} ('{name}') for project {project_id}")
        return automation

    def get_automation(self, automation_id: str) -> Automation | None:
        """Get automation by ID.

        Args:
            automation_id: Automation identifier

        Returns:
            Automation if found, None otherwise
        """
        automation_path = self.storage_dir / f"{automation_id}.json"
        if not automation_path.exists():
            return None

        try:
            data = json.loads(automation_path.read_text())
            return Automation.model_validate(data)
        except Exception as e:
            logger.error(f"Failed to load automation {automation_id}: {e}")
            return None

    def list_automations(
        self,
        project_id: str | None = None,
        enabled: bool | None = None,
    ) -> list[Automation]:
        """List automations with optional filters.

        Args:
            project_id: Filter by project (optional)
            enabled: Filter by enabled status (optional)

        Returns:
            List of matching Automation objects
        """
        # Load index for fast filtering
        index = self._load_index()

        # Filter automation IDs
        automation_ids = []
        for auto_id, entry in index.automations.items():
            # Apply filters
            if project_id is not None and entry.project_id != project_id:
                continue
            if enabled is not None and entry.enabled != enabled:
                continue

            automation_ids.append(auto_id)

        # Load full automation objects
        automations = []
        for auto_id in automation_ids:
            automation = self.get_automation(auto_id)
            if automation is not None:
                automations.append(automation)

        return automations

    def update_automation(self, automation_id: str, **updates) -> Automation:
        """Update automation fields.

        Args:
            automation_id: Automation to update
            **updates: Fields to update (name, message, schedule, enabled, etc.)

        Returns:
            Updated Automation

        Raises:
            ValueError: If automation not found
            ValueError: If name conflicts with another automation in same project

        Side Effects:
            Updates automation file atomically
            Updates index
        """
        automation = self.get_automation(automation_id)
        if automation is None:
            raise ValueError(f"Automation not found: {automation_id}")

        # Check for name conflicts if name is being updated
        if "name" in updates and updates["name"] != automation.name:
            existing = self.list_automations(project_id=automation.project_id)
            if any(auto.name == updates["name"] and auto.id != automation_id for auto in existing):
                raise ValueError(
                    f"Automation with name '{updates['name']}' already exists for project {automation.project_id}"
                )

        # Apply updates
        update_data = automation.model_dump()
        update_data.update(updates)
        update_data["updated_at"] = datetime.now(UTC)

        # Validate updated automation
        updated_automation = Automation.model_validate(update_data)

        # Write atomically
        automation_path = self.storage_dir / f"{automation_id}.json"
        tmp_path = automation_path.with_suffix(".tmp")
        tmp_path.write_text(updated_automation.model_dump_json(indent=2))
        tmp_path.rename(automation_path)

        # Update index
        self._update_index(updated_automation)

        logger.info(f"Updated automation {automation_id}")
        return updated_automation

    def delete_automation(self, automation_id: str) -> bool:
        """Delete automation and its execution history.

        Args:
            automation_id: Automation to delete

        Returns:
            True if deleted, False if not found

        Side Effects:
            Removes automation file
            Removes execution history file
            Updates index
        """
        automation_path = self.storage_dir / f"{automation_id}.json"
        executions_path = self.executions_dir / f"{automation_id}.jsonl"

        if not automation_path.exists():
            return False

        # Remove files
        automation_path.unlink()
        if executions_path.exists():
            executions_path.unlink()

        # Update index
        self._remove_from_index(automation_id)

        logger.info(f"Deleted automation {automation_id}")
        return True

    # --- Execution History ---

    def record_execution(
        self,
        automation_id: str,
        session_id: str,
        status: Literal["success", "failed"],
        error: str | None = None,
    ) -> ExecutionRecord:
        """Record an automation execution.

        Args:
            automation_id: Automation that was executed
            session_id: Session ID for this execution
            status: Execution outcome (success or failed)
            error: Error message if failed (optional)

        Returns:
            ExecutionRecord

        Side Effects:
            Appends to execution history: executions/{automation_id}.jsonl
            Updates automation last_execution timestamp
        """
        # Create execution record
        now = datetime.now(UTC)
        execution_id = str(uuid.uuid4())

        record = ExecutionRecord(
            id=execution_id,
            automation_id=automation_id,
            session_id=session_id,
            executed_at=now,
            status=status,
            error=error,
        )

        # Append to JSONL file
        executions_path = self.executions_dir / f"{automation_id}.jsonl"
        with executions_path.open("a") as f:
            f.write(record.model_dump_json() + "\n")

        # Update automation last_execution timestamp
        try:
            self.update_automation(automation_id, last_execution=now)
        except ValueError:
            # Automation might have been deleted - log but don't fail
            logger.warning(f"Failed to update last_execution for automation {automation_id}")

        logger.info(f"Recorded {status} execution {execution_id} for automation {automation_id}")
        return record

    def get_execution_history(
        self,
        automation_id: str,
        status: Literal["success", "failed"] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ExecutionRecord]:
        """Get execution history for automation.

        Args:
            automation_id: Automation to query
            status: Filter by status (optional)
            limit: Maximum number of records to return
            offset: Number of records to skip

        Returns:
            List of ExecutionRecord objects (newest first)
        """
        executions_path = self.executions_dir / f"{automation_id}.jsonl"
        if not executions_path.exists():
            return []

        # Read all records (JSONL format - one per line)
        records = []
        try:
            with executions_path.open("r") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        record = ExecutionRecord.model_validate(data)

                        # Apply status filter
                        if status is not None and record.status != status:
                            continue

                        records.append(record)
                    except Exception as e:
                        logger.warning(f"Failed to parse execution record: {e}")
                        continue
        except Exception as e:
            logger.error(f"Failed to read execution history: {e}")
            return []

        # Sort by executed_at descending (newest first)
        records.sort(key=lambda r: r.executed_at, reverse=True)

        # Apply pagination
        return records[offset : offset + limit]

    # --- Index Management ---

    def _load_index(self) -> AutomationIndex:
        """Load automation index from disk.

        Returns:
            AutomationIndex (empty if file doesn't exist)
        """
        if not self.index_path.exists():
            return AutomationIndex(automations={})

        try:
            data = json.loads(self.index_path.read_text())
            return AutomationIndex.model_validate(data)
        except Exception as e:
            logger.error(f"Failed to load automation index: {e}")
            return AutomationIndex(automations={})

    def _save_index(self, index: AutomationIndex) -> None:
        """Save automation index to disk atomically.

        Args:
            index: AutomationIndex to save
        """
        index.last_updated = datetime.now(UTC)

        tmp_path = self.index_path.with_suffix(".tmp")
        tmp_path.write_text(index.model_dump_json(indent=2))
        tmp_path.rename(self.index_path)

    def _update_index(self, automation: Automation) -> None:
        """Update index entry for automation.

        Args:
            automation: Automation to add/update in index
        """
        index = self._load_index()

        entry = AutomationIndexEntry(
            automation_id=automation.id,
            project_id=automation.project_id,
            name=automation.name,
            enabled=automation.enabled,
            next_execution=automation.next_execution,
        )

        index.automations[automation.id] = entry
        self._save_index(index)

    def _remove_from_index(self, automation_id: str) -> None:
        """Remove automation from index.

        Args:
            automation_id: Automation to remove
        """
        index = self._load_index()

        if automation_id in index.automations:
            del index.automations[automation_id]
            self._save_index(index)
