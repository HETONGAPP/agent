"""
Data collector tests
"""

import pytest

from src.collector.mock_collector import MockCollector


@pytest.mark.asyncio
async def test_mock_collector_alarms():
    """Test Mock collector alarm collection"""
    collector = MockCollector(source="BMS")
    alarms = await collector.collect_alarms()

    assert isinstance(alarms, list)
    # Mock collector may return 0-3 alarms
    assert 0 <= len(alarms) <= 3


@pytest.mark.asyncio
async def test_mock_collector_bms_data():
    """Test Mock collector BMS data"""
    collector = MockCollector(source="BMS")
    bms_data = await collector.get_bms_data("PACK_001")

    assert bms_data.pack_id == "PACK_001"
    assert len(bms_data.cell_voltages) == 4
    assert len(bms_data.temperatures) == 4
    assert 0 <= bms_data.soc <= 100
    assert 0 <= bms_data.soh <= 100


@pytest.mark.asyncio
async def test_mock_collector_context():
    """Test Mock collector context data"""
    collector = MockCollector(source="BMS")
    context = await collector.get_context_data("ALM_001")

    assert "alarm_id" in context
    assert "bms_data" in context
    assert "pack_id" in context
