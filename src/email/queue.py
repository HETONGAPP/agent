"""
Email Queue
Asynchronous email sending queue with rate limiting and deduplication
"""

import logging
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta, UTC
from collections import defaultdict

logger = logging.getLogger(__name__)


class EmailQueue:
    """
    Flexible email queue
    Supports rate limiting, deduplication, and async processing
    """

    def __init__(
        self,
        email_service: "EmailService",
        max_workers: int = 3,
        rate_limit: int = 10,  # emails per minute
        deduplication_window: int = 300,  # seconds
    ):
        """
        Initialize email queue

        Args:
            email_service: Email service instance
            max_workers: Maximum concurrent email sending workers
            rate_limit: Maximum emails per minute
            deduplication_window: Time window for deduplication (seconds)
        """
        self.email_service = email_service
        self.max_workers = max_workers
        self.rate_limit = rate_limit
        self.deduplication_window = deduplication_window

        self._queue: asyncio.Queue = asyncio.Queue()
        self._workers: List[asyncio.Task] = []
        self._sent_times: List[datetime] = []
        self._sent_alarms: Dict[str, datetime] = {}  # alarm_id -> last_sent_time
        self._running = False

    async def start(self):
        """Start email queue workers"""
        if self._running:
            return

        self._running = True
        self._workers = [
            asyncio.create_task(self._worker(f"worker-{i}"))
            for i in range(self.max_workers)
        ]
        logger.info(f"Email queue started with {self.max_workers} workers")

    async def stop(self):
        """Stop email queue workers"""
        self._running = False

        # Wait for queue to empty
        await self._queue.join()

        # Cancel workers
        for worker in self._workers:
            worker.cancel()

        await asyncio.gather(*self._workers, return_exceptions=True)
        logger.info("Email queue stopped")

    async def enqueue(
        self,
        alarm: "Alarm",
        diagnostic_report: Optional["DiagnosticReport"] = None,
        device_data: Optional[Dict[str, Any]] = None,
        custom_recipients: Optional[List[str]] = None,
        custom_subject: Optional[str] = None,
        force: bool = False,
    ) -> bool:
        """
        Enqueue email for sending

        Args:
            alarm: Alarm object
            diagnostic_report: Optional diagnostic report
            device_data: Optional device data
            custom_recipients: Optional custom recipients
            custom_subject: Optional custom subject
            force: Force send even if duplicate

        Returns:
            True if enqueued, False if duplicate or rate limited
        """
        # Check deduplication
        if not force and self._is_duplicate(alarm.alarm_id):
            logger.debug(f"Email for alarm {alarm.alarm_id} is duplicate, skipping")
            return False

        # Check rate limit
        if not force and self._is_rate_limited():
            logger.warning("Email rate limit reached, queuing for later")
            # Still enqueue, but mark as delayed
            await self._queue.put({
                "alarm": alarm,
                "diagnostic_report": diagnostic_report,
                "device_data": device_data,
                "custom_recipients": custom_recipients,
                "custom_subject": custom_subject,
                "delayed": True,
            })
            return True

        # Enqueue email
        await self._queue.put({
            "alarm": alarm,
            "diagnostic_report": diagnostic_report,
            "device_data": device_data,
            "custom_recipients": custom_recipients,
            "custom_subject": custom_subject,
            "delayed": False,
        })

        # Record alarm ID
        self._sent_alarms[alarm.alarm_id] = datetime.now(UTC)

        return True

    def _is_duplicate(self, alarm_id: str) -> bool:
        """Check if alarm email was recently sent"""
        if alarm_id not in self._sent_alarms:
            return False

        last_sent = self._sent_alarms[alarm_id]
        time_since_sent = (datetime.now(UTC) - last_sent).total_seconds()

        return time_since_sent < self.deduplication_window

    def _is_rate_limited(self) -> bool:
        """Check if rate limit is exceeded"""
        now = datetime.now(UTC)
        one_minute_ago = now - timedelta(minutes=1)

        # Remove old timestamps
        self._sent_times = [t for t in self._sent_times if t > one_minute_ago]

        return len(self._sent_times) >= self.rate_limit

    async def _worker(self, worker_name: str):
        """Email sending worker"""
        logger.info(f"Email worker {worker_name} started")

        while self._running:
            try:
                # Get email from queue (with timeout)
                try:
                    email_data = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                # Check rate limit
                if email_data.get("delayed") and self._is_rate_limited():
                    # Put back in queue
                    await self._queue.put(email_data)
                    await asyncio.sleep(10)  # Wait before retry
                    continue

                # Send email
                alarm = email_data["alarm"]
                success = await self.email_service.send_alarm_email(
                    alarm=alarm,
                    diagnostic_report=email_data.get("diagnostic_report"),
                    device_data=email_data.get("device_data"),
                    custom_recipients=email_data.get("custom_recipients"),
                    custom_subject=email_data.get("custom_subject"),
                )

                if success:
                    self._sent_times.append(datetime.now(UTC))

                # Mark task as done
                self._queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Email worker {worker_name} error: {e}", exc_info=True)
                self._queue.task_done()

        logger.info(f"Email worker {worker_name} stopped")

    def get_queue_size(self) -> int:
        """Get current queue size"""
        return self._queue.qsize()

    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        return {
            "queue_size": self._queue.qsize(),
            "workers": len(self._workers),
            "rate_limit": self.rate_limit,
            "emails_sent_last_minute": len([
                t for t in self._sent_times
                if (datetime.now(UTC) - t).total_seconds() < 60
            ]),
            "unique_alarms": len(self._sent_alarms),
        }


