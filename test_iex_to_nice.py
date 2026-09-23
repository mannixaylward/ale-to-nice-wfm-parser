import xml.etree.ElementTree as ET
from pathlib import Path

from iex_to_nice import parse_report, to_xml


SAMPLE = Path(__file__).parent / "upload" / "sample.iex"


def test_sample_is_consumed_into_three_nice_sections():
    report = parse_report(SAMPLE.read_text(encoding="utf-8"))
    assert report.start.strftime("%Y%m%dT%H%M") == "20260806T2015"
    assert len(report.queues) == 3
    assert len(report.agents) == 3

    root = to_xml(report).getroot()
    assert root.tag == "HistPlugin"
    assert len(root.findall("DataSourceNode/QueueNode/QueueData")) == 3
    assert len(root.findall("DataSourceNode/AgentQueueNode/AgentQueueData")) == 3
    assert len(root.findall("DataSourceNode/AgentSystemNode/AgentSystemData")) == 3
    ET.fromstring(ET.tostring(root))