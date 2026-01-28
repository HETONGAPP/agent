"""
Site container - Alarm operations mixin
Provides alarm write, query, and delete for site-specific data
"""
import logging
from typing import Any, Dict, List, Optional

from ..models.alarm import Alarm

logger = logging.getLogger(__name__)


class SiteAlarmMixin:
    """
    Mixin providing alarm operations for SiteContainer.
    Requires: self.site_id, self.bucket, self.influx_client, self.influx_client_base
    """

    def write_alarm(self, alarm: Alarm, flush: bool = False):
        """
        Write alarm to site container.
        Only keeps the latest snapshot for each alarm type (and device_id if present).
        """
        return self.influx_client.write_alarm(alarm, flush=flush, site_id=self.site_id)

    def query_alarms(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        alarm_id: Optional[str] = None,
        alarm_type: Optional[str] = None,
        severity: Optional[str] = None,
        device_type: Optional[str] = None,
        device_ids: Optional[List[str]] = None,
        limit: int = 100,
        deduplicate: bool = False,
    ) -> List[Dict[str, Any]]:
        """Query alarms from site container."""
        alarms = self.influx_client.query_alarms(
            start_time=start_time,
            end_time=end_time,
            alarm_id=alarm_id,
            alarm_type=alarm_type,
            severity=severity,
            device_type=device_type,
            limit=limit,
        )
        if device_ids:
            alarms = [alarm for alarm in alarms if alarm.get("device_id") in device_ids]
        for alarm in alarms:
            if not alarm.get("site_id"):
                alarm["site_id"] = self.site_id

        if deduplicate and alarms:
            from datetime import datetime

            alarm_groups: Dict[tuple, Dict[str, Any]] = {}
            for alarm in alarms:
                device_id = alarm.get("device_id", "")
                alarm_type_key = alarm.get("alarm_type", "")
                if not device_id:
                    aid = alarm.get("alarm_id", "")
                    if aid and "_" in aid:
                        parts = aid.split("_")
                        if len(parts) >= 2:
                            for part in parts[1:]:
                                if len(part) > 2 and any(c.isalpha() for c in part):
                                    device_id = part
                                    break
                if not device_id:
                    device_id = "UNKNOWN"
                if not alarm_type_key:
                    alarm_type_key = "UNKNOWN"
                key = (device_id, alarm_type_key)
                timestamp_str = alarm.get("timestamp", "")
                try:
                    timestamp = (
                        datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                        if isinstance(timestamp_str, str)
                        else timestamp_str
                    )
                except Exception:
                    continue
                if key not in alarm_groups:
                    alarm_groups[key] = alarm
                else:
                    existing_ts = alarm_groups[key].get("timestamp", "")
                    try:
                        existing_timestamp = (
                            datetime.fromisoformat(existing_ts.replace("Z", "+00:00"))
                            if isinstance(existing_ts, str)
                            else existing_ts
                        )
                        if timestamp > existing_timestamp:
                            alarm_groups[key] = alarm
                    except Exception:
                        pass
            alarms = list(alarm_groups.values())
            alarms.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            alarms = alarms[:limit]
        return alarms

    def delete_alarms(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        alarm_type: Optional[str] = None,
        alarm_id: Optional[str] = None,
        device_ids: Optional[List[str]] = None,
        rule_id: Optional[str] = None,
    ) -> int:
        """Delete alarms from site container."""
        from datetime import datetime, timedelta, UTC

        query_limit = 50000 if rule_id else 10000
        rule_start_time = (datetime.now(UTC) - timedelta(days=90)).isoformat() if rule_id and not start_time else start_time
        alarms = self.query_alarms(
            start_time=rule_start_time if rule_id else start_time,
            end_time=end_time,
            alarm_type=alarm_type,
            alarm_id=alarm_id,
            device_ids=device_ids,
            limit=query_limit,
        )
        if rule_id and alarms:
            filtered = []
            for alarm in alarms:
                meta = alarm.get("metadata")
                alarm_rule_id = meta.get("rule_id") if isinstance(meta, dict) else None
                if alarm_rule_id == rule_id or (alarm.get("alarm_id") or "").startswith(f"{rule_id}_"):
                    filtered.append(alarm)
            alarms = filtered

        try:
            delete_api = self.influx_client_base.client.delete_api()
            predicate = '_measurement="alarms"'
            if alarm_type:
                predicate += f' AND alarm_type="{alarm_type}"'
            if alarm_id:
                predicate += f' AND alarm_id="{alarm_id}"'
            if device_ids:
                predicate += " AND (" + " OR ".join(f'device_id="{d}"' for d in device_ids) + ")"
            if start_time:
                start = start_time
            elif rule_id:
                start = datetime.now(UTC) - timedelta(days=90)
            else:
                start = datetime.now(UTC) - timedelta(days=30)
            if end_time:
                stop = end_time
            else:
                stop = datetime.now(UTC) + timedelta(days=1)

            if rule_id:
                deleted_count = 0
                if alarms:
                    for alarm in alarms:
                        aid = alarm.get("alarm_id")
                        if aid:
                            try:
                                delete_api.delete(
                                    start=start, stop=stop,
                                    predicate=f'_measurement="alarms" AND alarm_id="{aid}"',
                                    bucket=self.bucket, org=self.influx_client_base.org,
                                )
                                deleted_count += 1
                            except Exception as e:
                                logger.warning(f"Failed to delete alarm {aid}: {e}")
                else:
                    logger.debug(f"No alarms found in query for rule_id {rule_id}, trying alternative deletion method")
                    all_alarms = self.query_alarms(start_time=start_time, end_time=end_time, limit=50000)
                    for alarm in all_alarms:
                        aid = alarm.get("alarm_id", "")
                        meta = alarm.get("metadata", {}) or {}
                        rid = meta.get("rule_id") if isinstance(meta, dict) else None
                        if rid == rule_id or aid.startswith(f"{rule_id}_"):
                            try:
                                delete_api.delete(
                                    start=start, stop=stop,
                                    predicate=f'_measurement="alarms" AND alarm_id="{aid}"',
                                    bucket=self.bucket, org=self.influx_client_base.org,
                                )
                                deleted_count += 1
                            except Exception as e:
                                logger.warning(f"Failed to delete alarm {aid}: {e}")
                logger.info(f"Deleted {deleted_count} alarms for rule {rule_id} from site {self.site_id}")
                return deleted_count
            delete_api.delete(start=start, stop=stop, predicate=predicate, bucket=self.bucket, org=self.influx_client_base.org)
            cnt = len(alarms)
            logger.info(f"Deleted {cnt} alarms from site {self.site_id}")
            return cnt
        except Exception as e:
            logger.error(f"Failed to delete alarms from site {self.site_id}: {e}", exc_info=True)
            return 0
