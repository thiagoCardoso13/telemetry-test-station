# Simulator

A toy pressurised tank that talks the [link protocol](PROTOCOL.md) over UDP. The physics is chosen to
be watchable on a dashboard, **not** to model a real tank.

```bash
python -m station.simulator --seed 1
```

It listens for commands on `127.0.0.1:5001` and sends telemetry to `127.0.0.1:5002`
(`--listen` and `--telemetry` change this). It binds to loopback by default because the link has no
authentication.

Every 100 ms it advances the physics, sends any new events and then one housekeeping report.

## Behaviour

Pressures are gauge: 0 bar is the outside air. The tank starts at 2 bar and 20 degC.

| Action | Effect |
|---|---|
| Fill valve open | Pressure rises towards the 10 bar supply |
| Vent valve open | Pressure falls towards 0 |
| Relief valve | Cannot be commanded: opens at 7.5 bar, closes at 6.5 bar |
| Pressure change | Temperature follows it, then drifts back to 20 degC |

## Faults

| Fault | Magnitude | Effect |
|---|---|---|
| leak | rate per second, above 0 and up to 1 | Pressure drains |
| noisy_sensor | standard deviation in bar, above 0 and up to 2 | Reported pressure is noisy; the tank is not affected |
| stuck_valve | 1 = fill, 2 = vent, 3 = relief | The valve stays where it is |

`clear_faults` removes them. `reset` also restores the initial state and restarts the random generator.

With a stuck relief valve and the fill valve open, pressure passes the 8 bar limit. This is the case
a test sequence is meant to catch.

## Reproducibility

The physics uses a fixed time step and a seeded random generator. The same seed, commands and step
numbers produce the same readings. Over a real network a command can arrive one step earlier or later,
so exact repetition is guaranteed when the simulator is driven in-process, as the tests do.
