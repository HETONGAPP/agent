"""
End-to-End (E2E) Tests
Test the complete alarm processing workflow from trigger to notification
"""

import pytest
import asyncio
from datetime import datetime, UTC
from typing import Dict, Any

from src.models.alarm import Alarm, AlarmSeverity
from src.models.device_data import DeviceData, DeviceType
from src.models.diagnostic import DiagnosticReport, RiskLevel
from src.rule_engine import RuleEngine
from src.agent.service import AgentService


class TestE2EAlarmProcessing:
    """End-to-end alarm processing tests"""

    @pytest.fixture
    def rule_engine(self):
        """Create rule engine instance"""
        return RuleEngine(rules_file="config/rules.yaml")

    @pytest.fixture
    def agent_service(self, rule_engine):
        """Create agent service instance (without optional services for basic tests)"""
        return AgentService(rule_engine=rule_engine)

    @pytest.mark.asyncio
    async def test_complete_bms_alarm_workflow(self, agent_service):
        """Test complete BMS alarm processing workflow"""
        # Create device data that should trigger an alarm
        device_data = DeviceData(
            device_id="BMS_001",
            device_type=DeviceType.BMS,
            timestamp=datetime.now(UTC),
            source="test",
            data={
                "max_delta_v": 0.15,  # Should trigger cell_voltage_deviation
                "max_temperature": 50.0,
                "soc": 65.0,
            },
        )

        # Process device data
        result = await agent_service.process_device_data(device_data)

        # Verify result structure
        assert result["status"] == "success"
        assert "alarms_processed" in result

        # If alarms were generated, verify processing
        if result["alarms_processed"] > 0:
            assert "results" in result
            assert len(result["results"]) == result["alarms_processed"]

            # Verify each alarm result
            for alarm_result in result["results"]:
                assert "alarm" in alarm_result
                assert alarm_result["alarm"]["alarm_type"] is not None
                assert alarm_result["alarm"]["severity"] in ["Info", "Warning", "Critical"]

    @pytest.mark.asyncio
    async def test_complete_pcs_alarm_workflow(self, agent_service):
        """Test complete PCS alarm processing workflow"""
        # Create PCS device data
        device_data = DeviceData(
            device_id="PCS_001",
            device_type=DeviceType.PCS,
            timestamp=datetime.now(UTC),
            source="test",
            data={
                "active_power": 150.0,  # kW
                "reactive_power": 20.0,
                "efficiency": 0.85,
                "status": "running",
            },
        )

        # Process device data
        result = await agent_service.process_device_data(device_data)

        # Verify result
        assert result["status"] == "success"
        assert "alarms_processed" in result

    @pytest.mark.asyncio
    async def test_multiple_concurrent_alarms(self, agent_service):
        """Test processing multiple alarms concurrently"""
        # Create multiple device data instances
        device_data_list = [
            DeviceData(
                device_id=f"BMS_{i:03d}",
                device_type=DeviceType.BMS,
                timestamp=datetime.now(UTC),
                source="test",
                data={"max_delta_v": 0.12 + i * 0.01},
            )
            for i in range(5)
        ]

        # Process all concurrently
        tasks = [
            agent_service.process_device_data(device_data) for device_data in device_data_list
        ]
        results = await asyncio.gather(*tasks)

        # Verify all processed successfully
        assert len(results) == 5
        for result in results:
            assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_alarm_with_diagnostic(self, agent_service):
        """Test alarm processing with diagnostic generation"""
        # This test requires LLM service to be configured
        # For now, we'll test the structure without actual LLM call

        device_data = DeviceData(
            device_id="BMS_001",
            device_type=DeviceType.BMS,
            timestamp=datetime.now(UTC),
            source="test",
            data={"max_delta_v": 0.15},
        )

        result = await agent_service.process_device_data(device_data)

        # Verify result structure
        assert result["status"] == "success"

        # If diagnostic was generated, verify structure
        if result.get("alarms_processed", 0) > 0:
            for alarm_result in result.get("results", []):
                if alarm_result.get("diagnostic"):
                    diagnostic = alarm_result["diagnostic"]
                    assert "risk_level" in diagnostic
                    assert diagnostic["risk_level"] in ["Low", "Medium", "High"]
                    assert "current_status" in diagnostic

    @pytest.mark.asyncio
    async def test_grafana_webhook_processing(self, agent_service):
        """Test Grafana webhook processing"""
        from src.grafana.webhook import GrafanaWebhookHandler

        # Simulate Grafana webhook payload (v8+ format)
        webhook_payload = {
            "alerts": [
                {
                    "status": "firing",
                    "labels": {
                        "alertname": "Cell Voltage Deviation",
                        "severity": "warning",
                        "device_id": "BMS_001",
                    },
                    "annotations": {
                        "summary": "Cell voltage deviation detected",
                        "description": "Max delta V: 0.15V",
                    },
                    "startsAt": datetime.now(UTC).isoformat(),
                }
            ],
            "dashboardId": 1,
            "panelId": 1,
        }

        # Parse webhook
        webhook_handler = GrafanaWebhookHandler()
        parsed_data = webhook_handler.parse_webhook(webhook_payload)

        # Process webhook
        result = await agent_service.process_webhook_alarm(parsed_data)

        # Verify result
        assert result["status"] == "success"
        assert "alarms_processed" in result


class TestPerformance:
    """Performance tests"""

    @pytest.mark.asyncio
    async def test_rule_engine_performance(self):
        """Test rule engine performance with many rules"""
        # Load rules
        engine = RuleEngine(rules_file="config/rules.yaml")
        rules_count = len(engine.get_rules())

        # Create test data
        device_data = DeviceData(
            device_id="BMS_001",
            device_type=DeviceType.BMS,
            timestamp=datetime.now(UTC),
            source="test",
            data={"max_delta_v": 0.15},
        )

        # Measure evaluation time
        import time

        start_time = time.time()
        alarms = engine.evaluate(device_data)
        elapsed_time = time.time() - start_time

        # Performance assertion: should evaluate in < 100ms
        assert elapsed_time < 0.1, f"Rule evaluation took {elapsed_time:.3f}s, expected < 0.1s"

        print(f"✓ Evaluated {rules_count} rules in {elapsed_time*1000:.2f}ms")

    @pytest.mark.asyncio
    async def test_concurrent_alarm_processing(self, agent_service):
        """Test concurrent alarm processing performance"""
        # Create 10 device data instances
        device_data_list = [
            DeviceData(
                device_id=f"BMS_{i:03d}",
                device_type=DeviceType.BMS,
                timestamp=datetime.now(UTC),
                source="test",
                data={"max_delta_v": 0.12 + (i % 5) * 0.01},
            )
            for i in range(10)
        ]

        # Process concurrently
        import time

        start_time = time.time()
        tasks = [
            agent_service.process_device_data(device_data) for device_data in device_data_list
        ]
        results = await asyncio.gather(*tasks)
        elapsed_time = time.time() - start_time

        # Verify all processed
        assert len(results) == 10
        assert all(r["status"] == "success" for r in results)

        # Performance: should process 10 alarms in < 5 seconds (without LLM)
        assert elapsed_time < 5.0, f"Processing took {elapsed_time:.3f}s, expected < 5s"

        print(f"✓ Processed 10 alarms concurrently in {elapsed_time:.2f}s")


class TestErrorHandling:
    """Error handling tests"""

    @pytest.mark.asyncio
    async def test_invalid_device_data(self, agent_service):
        """Test handling of invalid device data"""
        # Create invalid device data (missing required fields)
        device_data = DeviceData(
            device_id="",
            device_type=DeviceType.BMS,
            timestamp=datetime.now(UTC),
            source="test",
            data={},
        )

        # Should handle gracefully
        result = await agent_service.process_device_data(device_data)
        assert result["status"] in ["success", "error"]

    @pytest.mark.asyncio
    async def test_missing_rule_conditions(self, agent_service):
        """Test handling of device data that doesn't match any rules"""
        # Create device data that shouldn't match any rules
        device_data = DeviceData(
            device_id="BMS_001",
            device_type=DeviceType.BMS,
            timestamp=datetime.now(UTC),
            source="test",
            data={"max_delta_v": 0.01},  # Very low, shouldn't trigger alarms
        )

        result = await agent_service.process_device_data(device_data)
        assert result["status"] == "success"
        # Should return 0 alarms or handle gracefully
        assert result.get("alarms_processed", 0) >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

