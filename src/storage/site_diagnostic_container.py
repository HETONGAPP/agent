"""
Site container - Diagnostic operations mixin
Provides diagnostic write, query, and delete for site-specific data
"""
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SiteDiagnosticMixin:
    """
    Mixin providing diagnostic operations for SiteContainer.
    Requires: self.site_id, self.bucket, self.influx_client, self.influx_client_base
    """

    def write_diagnostic(self, alarm_id: str, diagnostic: Dict[str, Any], flush: bool = False):
        """Write diagnostic to site container."""
        result = self.influx_client.write_diagnostic(alarm_id, diagnostic, site_id=self.site_id, flush=flush)
        if flush:
            self.influx_client.flush()
        return result

    def query_diagnostics(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        alarm_id: Optional[str] = None,
        risk_level: Optional[str] = None,
        device_type: Optional[str] = None,
        device_ids: Optional[List[str]] = None,
        limit: int = 100,
        deduplicate: bool = True,
    ) -> List[Dict[str, Any]]:
        """Query diagnostics from site container."""
        query_limit = limit * 3 if deduplicate else limit
        diagnostics = self.influx_client.query_diagnostics(
            start_time=start_time,
            end_time=end_time,
            alarm_id=alarm_id,
            risk_level=risk_level,
            device_type=device_type,
            limit=query_limit,
        )
        if device_ids:
            diagnostics = [d for d in diagnostics if d.get("device_id") in device_ids]
        for d in diagnostics:
            if not d.get("site_id"):
                d["site_id"] = self.site_id

        if deduplicate and diagnostics:
            from datetime import datetime

            groups: Dict[tuple, Dict[str, Any]] = {}
            for d in diagnostics:
                device_id = d.get("device_id", "")
                alarm_type_key = d.get("alarm_type", "")
                if not device_id:
                    aid = d.get("alarm_id", "")
                    if aid and "_" in aid:
                        for part in aid.split("_")[1:]:
                            if len(part) > 2 and any(c.isalpha() for c in part):
                                device_id = part
                                break
                if not alarm_type_key:
                    alarm_type_key = d.get("alarm_id", "") or "UNKNOWN"
                if not device_id:
                    device_id = "UNKNOWN"
                if not alarm_type_key:
                    alarm_type_key = "UNKNOWN"
                key = (device_id, alarm_type_key)
                ts = d.get("timestamp", "")
                try:
                    t = datetime.fromisoformat(ts.replace("Z", "+00:00")) if isinstance(ts, str) else ts
                except Exception:
                    continue
                if key not in groups:
                    groups[key] = d
                else:
                    ets = groups[key].get("timestamp", "")
                    try:
                        et = datetime.fromisoformat(ets.replace("Z", "+00:00")) if isinstance(ets, str) else ets
                        if t > et:
                            groups[key] = d
                    except Exception:
                        pass
            diagnostics = list(groups.values())
            diagnostics.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            diagnostics = diagnostics[:limit]
        return diagnostics

    def delete_diagnostics(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        risk_level: Optional[str] = None,
        alarm_id: Optional[str] = None,
        device_ids: Optional[List[str]] = None,
    ) -> int:
        """Delete diagnostics from site container."""
        diagnostics = self.query_diagnostics(
            start_time=start_time,
            end_time=end_time,
            risk_level=risk_level,
            alarm_id=alarm_id,
            device_ids=device_ids,
            limit=10000,
        )
        if not diagnostics:
            return 0
        try:
            from datetime import datetime, timedelta, UTC

            delete_api = self.influx_client_base.client.delete_api()
            predicate = '_measurement="diagnostics"'
            if risk_level:
                predicate += f' AND risk_level="{risk_level}"'
            if alarm_id:
                predicate += f' AND alarm_id="{alarm_id}"'
            if device_ids:
                predicate += " AND (" + " OR ".join(f'device_id="{d}"' for d in device_ids) + ")"
            start = start_time if start_time else datetime.now(UTC) - timedelta(days=30)
            stop = end_time if end_time else datetime.now(UTC) + timedelta(days=1)
            delete_api.delete(start=start, stop=stop, predicate=predicate, bucket=self.bucket, org=self.influx_client_base.org)
            logger.info(f"Deleted {len(diagnostics)} diagnostics from site {self.site_id}")
            return len(diagnostics)
        except Exception as e:
            logger.error(f"Failed to delete diagnostics from site {self.site_id}: {e}", exc_info=True)
            return 0

    def delete_diagnostic(self, alarm_id: str) -> bool:
        """Delete diagnostic report from site container."""
        try:
            return self.influx_client.delete_diagnostic(alarm_id, site_id=self.site_id)
        except Exception as e:
            logger.error(f"Failed to delete diagnostic from site {self.site_id}: {e}", exc_info=True)
            return False
