# Link protocol

How the ground station and the simulated tank talk to each other. The framing is **inspired by**
CCSDS Space Packets and ECSS PUS and implements only the subset below. It is **not compliant** with
either standard.

One UDP datagram carries exactly one packet. All numbers are big-endian.

## Packet layout

| Offset | Size | Field | Content |
|---|---|---|---|
| 0 | 2 | Identification | 3 bits version (`000`), 1 bit type (0 telemetry, 1 telecommand), 1 bit secondary header flag (`1`), 11 bits APID (`100` for the tank) |
| 2 | 2 | Sequence control | 2 bits sequence flags (`11`, unsegmented), 14 bits sequence count |
| 4 | 2 | Data length | Number of bytes after offset 5, minus one |
| 6 | 1 | Service | See below |
| 7 | 1 | Subservice | See below |
| 8 | 8 | Time | Milliseconds since the Unix epoch |
| 16 | n | Payload | Depends on service and subservice |
| 16 + n | 2 | CRC | CRC-16/CCITT-FALSE of every byte before it |

The smallest packet is 18 bytes. The sequence count wraps from 16383 to 0.

### Differences from the standards

- The secondary header is the same for telemetry and telecommands, and much shorter than in PUS.
- Time is a Unix timestamp, not a CCSDS time code.
- No segmentation, no acknowledgement flags, no source or destination identifiers.

## Services

| Packet | Meaning | Payload |
|---|---|---|
| TM(1,1) / TM(1,2) | Command accepted / rejected | request id (4), error code (1, only when rejected) |
| TM(1,7) / TM(1,8) | Command completed / failed | request id (4), error code (1, only when failed) |
| TM(3,25) | Housekeeping report | structure id (1, always `1`), parameter values |
| TM(5,1..4) | Event: info, low, medium, high severity | event id (2), value (float32) |
| TC(8,1) | Perform a function | function id (1), arguments |
| TC(17,1) / TM(17,2) | Are you alive / yes | empty |

The **request id** is the first four bytes (identification and sequence control) of the command
being reported on. Error code values are defined with the simulator.

## Parameters, functions and events

[`definitions.yaml`](../station/src/station/protocol/definitions.yaml) is the single source of truth.
The housekeeping report carries the parameters in the order listed there:

| Parameter | Type | Unit | Limits |
|---|---|---|---|
| tank_pressure | float32 | bar | 0.5 to 8.0 |
| tank_temperature | float32 | degC | -20 to 60 |
| fill_valve | uint8 | 1 = open | |
| vent_valve | uint8 | 1 = open | |
| relief_valve | uint8 | 1 = open | |

| Function id | Name | Arguments |
|---|---|---|
| 1 | set_valve | valve (uint8: fill = 1, vent = 2), open (uint8) |
| 2 | inject_fault | fault (uint8: leak = 1, stuck_valve = 2, noisy_sensor = 3), magnitude (float32) |
| 3 | clear_faults | none |
| 4 | reset | none |

| Event id | Name | Severity |
|---|---|---|
| 1 | relief_valve_opened | medium |
| 2 | relief_valve_closed | info |
| 3 | fault_injected | info |

## Rejected packets

The decoder never guesses. Every rejection has a reason, so it can be counted.

| Reason | When |
|---|---|
| `too_short` | Fewer than 18 bytes |
| `length_mismatch` | Data length disagrees with the datagram size |
| `bad_crc` | Checksum does not match |
| `unsupported` | Unknown version, APID or service; segmented; no secondary header |
| `bad_payload` | Payload does not fit the service |

A CRC detects accidental corruption. It gives **no protection against a malicious sender**: there is
no authentication on this link.

## Worked examples

Both use sequence count 1 and time 1700000000000. A test checks that these bytes stay correct.

Command: open the vent valve, TC(8,1).

```text
18 64 c0 01 00 0e 08 01 00 00 01 8b cf e5 68 00 01 02 01 8b a4
```

| Bytes | Meaning |
|---|---|
| `18 64` | telecommand, secondary header, APID 100 |
| `c0 01` | unsegmented, sequence 1 |
| `00 0e` | 15 bytes follow |
| `08 01` | service 8, subservice 1 |
| `00 00 01 8b cf e5 68 00` | time |
| `01 02 01` | set_valve, vent, open |
| `8b a4` | CRC |

Housekeeping report, TM(3,25): 2.5 bar, 21 degC, fill valve open.

```text
08 64 c0 01 00 17 03 19 00 00 01 8b cf e5 68 00 01 40 20 00 00 41 a8 00 00 01 00 00 b3 40
```
