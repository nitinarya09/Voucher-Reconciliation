# -*- coding: utf-8 -*-
"""
Audit Log Module
Maintains run IDs, execution parameters, audit events, warnings, errors, and export history.
"""

import os
import json
import uuid
import datetime

class AuditLogger:
    def __init__(self, log_dir=None):
        self.run_id = str(uuid.uuid4())
        self.timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_dir = log_dir or os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
        os.makedirs(self.log_dir, exist_ok=True)
        
        self.events = []
        self.warnings = []
        self.errors = []
        self.export_history = []
        self.metadata = {}

    def log_event(self, stage, message):
        entry = {
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "stage": stage,
            "message": message,
            "type": "INFO"
        }
        self.events.append(entry)

    def log_warning(self, stage, message):
        entry = {
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "stage": stage,
            "message": message,
            "type": "WARNING"
        }
        self.warnings.append(entry)
        self.events.append(entry)

    def log_error(self, stage, message):
        entry = {
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "stage": stage,
            "message": message,
            "type": "ERROR"
        }
        self.errors.append(entry)
        self.events.append(entry)

    def log_export(self, export_type, file_path, record_count=0):
        entry = {
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "export_type": export_type,
            "file_path": file_path,
            "filename": os.path.basename(file_path),
            "record_count": record_count
        }
        self.export_history.append(entry)

    def set_metadata(self, key, value):
        self.metadata[key] = value

    def save_log(self):
        """Persists audit log to JSON file in logs/ directory."""
        filename = f"reconciliation_log_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{self.run_id[:8]}.json"
        out_path = os.path.join(self.log_dir, filename)
        log_data = {
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
            "total_events": len(self.events),
            "total_warnings": len(self.warnings),
            "total_errors": len(self.errors),
            "export_history": self.export_history,
            "events": self.events
        }
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, indent=2)
        return out_path
