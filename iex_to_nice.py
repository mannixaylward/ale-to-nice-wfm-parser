#!/usr/bin/env python3
"""Convert an IEX text report into a NICE Import History XML report."""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


REPORT_RE = re.compile(
    r"^(CALL GROUP REPORT|AGENT DETAIL REPORT)\s+(\d{2}/\d{2}/\d{2})\s+"
    r"(\d{2}:\d{2})-(\d{2}:\d{2})$"
)

INPUTDIR = "input"
INPUTFILE = "sample.iex"
OUTPUTDIR = "output"
VENDOR = "IEX"


@dataclass(frozen=True)
class QueueRecord:
    queue: str
    answer: int
    abandon: int
    answered_short: int
    abandoned_short: int
    delay_seconds: int
    talk_seconds: int


@dataclass(frozen=True)
class AgentRecord:
    agent: str
    queue: str
    handled: int
    handle_seconds: int
    ready_seconds: int
    work_seconds: int


@dataclass(frozen=True)
class Report:
    start: datetime
    end_time: str
    queues: tuple[QueueRecord, ...]
    agents: tuple[AgentRecord, ...]


def _integer(value: str, line_number: int) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"line {line_number}: expected integer, got {value!r}") from exc
    if parsed < 0:
        raise ValueError(f"line {line_number}: values cannot be negative")
    return parsed


def _find_section(lines: list[str], heading: str) -> tuple[int, str, str]:
    for index, line in enumerate(lines):
        match = REPORT_RE.match(line)
        if match and match.group(1) == heading:
            return index, match.group(2), match.group(4)
    raise ValueError(f"missing {heading} section")


def _next_nonempty(lines: list[str], start: int) -> tuple[int, str]:
    for index in range(start, len(lines)):
        if lines[index].strip():
            return index, lines[index].strip()
    raise ValueError("unexpected end of report")


def parse_report(text: str) -> Report:
    lines = [line.strip() for line in text.splitlines()]
    queue_index, date_text, _ = _find_section(lines, "CALL GROUP REPORT")
    agent_index, agent_date_text, _ = _find_section(lines, "AGENT DETAIL REPORT")
    if date_text != agent_date_text:
        raise ValueError("queue and agent sections use different dates")

    header_index, header = _next_nonempty(lines, queue_index + 1)
    if header != "PILOT ANSWER ABAND ANS ABAN DELAY DELAY TALK":
        raise ValueError(f"unexpected call-group header: {header!r}")

    queues: list[QueueRecord] = []
    for line_number, line in enumerate(lines[header_index + 1 : agent_index], header_index + 2):
        if not line:
            continue
        fields = line.split()
        if len(fields) != 7:
            raise ValueError(f"line {line_number}: expected pilot plus 6 numeric values")
        values = [_integer(value, line_number) for value in fields[1:]]
        queues.append(QueueRecord(fields[0], *values))

    agent_header_index, agent_header = _next_nonempty(lines, agent_index + 1)
    if agent_header != "PILOT LOG_ID IN_CALLS IN_SEC READY_SEC WORK_SEC":
        raise ValueError(f"unexpected agent header: {agent_header!r}")

    agents: list[AgentRecord] = []
    for line_number, line in enumerate(lines[agent_header_index + 1 :], agent_header_index + 2):
        if not line:
            continue
        fields = line.split()
        if len(fields) != 6:
            raise ValueError(f"line {line_number}: expected pilot, agent, and 4 numeric values")
        values = [_integer(value, line_number) for value in fields[2:]]
        agents.append(AgentRecord(fields[0], fields[1], *values))

    if not queues:
        raise ValueError("call-group section contains no data")
    if not agents:
        raise ValueError("agent section contains no data")

    start_time = lines[queue_index].split()[4].split("-", 1)[0]
    start = datetime.strptime(date_text + " " + start_time, "%m/%d/%y %H:%M")
    return Report(start, lines[queue_index].split("-")[-1], tuple(queues), tuple(agents))


def _duration(parent: ET.Element, name: str, seconds: int) -> None:
    element = ET.SubElement(parent, name)
    duration = ET.SubElement(element, "duration")
    ET.SubElement(duration, "totalseconds").text = str(seconds)


def _count(parent: ET.Element, name: str, value: int) -> None:
    element = ET.SubElement(parent, name)
    ET.SubElement(element, "count").text = str(value)


def to_xml(report: Report, vendor: str = "IEX") -> ET.ElementTree:
    root = ET.Element("HistPlugin")
    timestamp = report.start.strftime("%Y%m%dT%H%M")

    queue_source = ET.SubElement(root, "DataSourceNode")
    ET.SubElement(queue_source, "Vendor").text = vendor
    queue_node = ET.SubElement(queue_source, "QueueNode")
    period = ET.SubElement(queue_node, "TimePeriod")
    ET.SubElement(period, "DateTime").text = timestamp
    for record in report.queues:
        data = ET.SubElement(queue_node, "QueueData")
        ET.SubElement(data, "QueueValue").text = record.queue
        _count(data, "ContactsReceived", record.answer + record.abandon)
        _count(data, "AbandonedLong", record.abandon)
        _count(data, "HandledShort", record.answered_short)
        _count(data, "AbandonedShort", record.abandoned_short)
        _duration(data, "HandleTime", record.talk_seconds)
        _duration(data, "QueueDelayTime", record.delay_seconds)

    agent_queue_source = ET.SubElement(root, "DataSourceNode")
    ET.SubElement(agent_queue_source, "Vendor").text = vendor
    agent_queue_node = ET.SubElement(agent_queue_source, "AgentQueueNode")
    period = ET.SubElement(agent_queue_node, "TimePeriod")
    ET.SubElement(period, "DateTime").text = timestamp
    for record in report.agents:
        data = ET.SubElement(agent_queue_node, "AgentQueueData")
        ET.SubElement(data, "QueueValue").text = record.queue
        ET.SubElement(data, "AgentValue").text = record.agent
        _count(data, "Handled", record.handled)
        _duration(data, "HandleTime", record.handle_seconds)
        _duration(data, "WorkTime", record.work_seconds)

    agent_system_source = ET.SubElement(root, "DataSourceNode")
    ET.SubElement(agent_system_source, "Vendor").text = vendor
    agent_system_node = ET.SubElement(agent_system_source, "AgentSystemNode")
    period = ET.SubElement(agent_system_node, "TimePeriod")
    ET.SubElement(period, "DateTime").text = timestamp
    for record in report.agents:
        data = ET.SubElement(agent_system_node, "AgentSystemData")
        ET.SubElement(data, "AgentValue").text = record.agent
        _duration(data, "ReadyTime", record.ready_seconds)

    ET.indent(root, space="  ")
    return ET.ElementTree(root)


def main() -> int:
    try:
        report = parse_report(Path(INPUTDIR + "/" + INPUTFILE).read_text(encoding="utf-8"))
        tree = to_xml(report, VENDOR)
        tree.write(Path(OUTPUTDIR + "/TEST_" + datetime.now().strftime("%m%d%y.%H%M%S") + ".xml"), encoding="utf-8", xml_declaration=True)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())