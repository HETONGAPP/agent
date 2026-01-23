"""
Data model tests
"""

from datetime import datetime


from src.models.alarm import Alarm, AlarmSeverity
from src.models.bms_data import BMSData
from src.models.diagnostic import DiagnosticReport, RiskLevel


def test_alarm_creation():
    """Test alarm creation"""
    alarm = Alarm(
        alarm_id="ALM_001",
        alarm_type="Cell Voltage Deviation",
        severity=AlarmSeverity.WARNING,
        timestamp=datetime.now(),
        source="BMS",
    )

    assert alarm.alarm_id == "ALM_001"
    assert alarm.severity == AlarmSeverity.WARNING
    assert alarm.to_dict()["alarm_id"] == "ALM_001"


def test_bms_data_properties():
    """Test BMS data properties"""
    bms_data = BMSData(
        timestamp=datetime.now(),
        cell_voltages=[3.5, 3.6, 3.4, 3.55],
        temperatures=[25, 26, 24, 27],
        soc=80.0,
        soh=95.0,
        max_delta_v=0.2,
        pack_id="PACK_001",
    )

    assert bms_data.max_voltage == 3.6
    assert bms_data.min_voltage == 3.4
    assert bms_data.max_temperature == 27
    assert bms_data.min_temperature == 24


def test_diagnostic_report():
    """Test diagnostic report"""
    report = DiagnosticReport(
        alarm_id="ALM_001",
        current_status="Voltage deviation detected",
        risk_level=RiskLevel.MEDIUM,
        possible_causes=["Uneven cooling", "Cell aging"],
        recommended_actions=["Check cooling system", "Review within 24h"],
    )

    assert report.risk_level == RiskLevel.MEDIUM
    assert len(report.possible_causes) == 2
