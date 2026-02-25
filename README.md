<h1 align="center">Flying a Virtual Drone with PX4 and Gazebo</h1>

<p align="center">
    <strong>Practical Simulation and Testing Workflows for PX4-Based Drones</strong>
</p>
<p align="center">
    <em>A Packt Publishing Workshop</em>
</p>

## About

Stop worrying about crashing expensive hardware and start mastering the skies in a digital sandbox.
This workshop bridges the gap between theoretical robotics and real-world UAV deployment by focusing on the industry-standard **Software-In-The-Loop (SITL)** workflow used by top aerospace and tech companies to develop autonomous flight systems.

Too often, teams trust ideal simulation results without testing edge-case failures.
This workshop helps you avoid that risk by surfacing real-world constraints **before** they become real-world problems.

We move rapidly from environment configuration to executing complex, code-driven missions — ensuring you leave with a fully functional development environment and the confidence to script autonomous behaviors from scratch.

This repository contains all the materials for the workshop.

## What You'll Walk Away With

- A working **PX4 + Gazebo** simulation environment configured for realistic autonomy testing.
- Practical mission scripts using **MAVSDK** to control and test drone behavior in simulation.
- Hands-on experience introducing and observing common failure scenarios such as GPS loss and motor issues.
- The ability to analyze PX4 logs with **PlotJuggler** and understand why autonomous behavior succeeded or failed.
- A clearer way to judge whether simulation results are reliable enough to inform next-stage testing decisions.
- Reusable setup files, scripts, and examples you can adapt to your own autonomy or validation workflows.

## Outline

| # | Session | Time (EDT) |
|---|---------|------------|
| 1 | Networking & Environment Setup | 9:00 – 9:30 |
| 2 | Welcome & Context Setting | 9:30 – 9:45 |
| 3 | SITL Environment Setup | 9:45 – 10:30 |
| 4 | Manual & Scripted Missions | 10:30 – 11:15 |
| 5 | Log Inspection & Behavior Verification | 11:15 – 11:45 |
| 6 | Break | 11:45 – 12:15 |
| 7 | Environment & Model Modifications | 12:15 – 12:45 |
| 8 | Failure Scenario Injection | 12:45 – 1:15 |
| 9 | Multi-Instance Simulation | 1:15 – 1:40 |
| 10 | Log-Driven Analysis & Wrap-Up | 1:40 – 2:00 |

**Note:** Each session includes exercises designed to reinforce the concepts, deepen understanding, and encourage exploration of the environment.

## Environment Setup

For detailed environment and Docker setup instructions, see the [docs/setup.md](docs/setup.md) guide.
Prerequisites installation instructions are available in [docs/prerequisites.md](docs/prerequisites.md).

**Please complete these steps before the workshop begins.**

## Who Should Attend

- Autonomy, robotics, or firmware engineers developing, testing, or reviewing drone flight behavior.
- Validation engineers testing or signing off on autonomous drone behavior before deployment.
- Senior engineers or technical leads who act on simulation results and defend those decisions to stakeholders.
- Platform or CI engineers supporting autonomy testing and validation pipelines.

This is not a fundamentals-only or demo-driven session. It is designed for engineers who need **decision-grade evidence**, not just working demos.

## What You'll Need

- A laptop capable of running PX4 and Gazebo simulation.
- Windows (with Docker Desktop and WSL2), macOS, or Linux (Ubuntu 22/24 recommended).
- Docker installed and running before the session.
- Basic working knowledge of Python.
- Comfort using the Linux command line.
- VS Code installed with Docker extensions.
- **No physical drone hardware is required** — all exercises are completed in simulation.
