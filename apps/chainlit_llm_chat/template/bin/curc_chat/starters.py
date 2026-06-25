"""HPC-themed conversation starters for the Chainlit welcome screen."""

import chainlit as cl

HPC_STARTERS = [
    cl.Starter(
        label="Cluster computing basics",
        message=(
            "Explain high-performance computing in plain language: login vs compute nodes, "
            "job schedulers, queues, and why shared clusters are different from a laptop."
        ),
        icon="/public/learn.svg",
    ),
    cl.Starter(
        label="Plan a batch workflow",
        message=(
            "Walk me through a typical batch workflow on a shared cluster: choosing resources, "
            "submitting a job, monitoring progress, and collecting outputs. Keep it conceptual."
        ),
        icon="/public/workflow.svg",
    ),
    cl.Starter(
        label="Python on shared systems",
        message=(
            "What are good practices for running Python on a shared HPC system? "
            "Cover virtual environments, dependencies, and being a good neighbor on shared storage."
        ),
        icon="/public/terminal.svg",
    ),
    cl.Starter(
        label="Debug a stuck job",
        message=(
            "My batch job seems stuck or much slower than expected. "
            "Give me a practical troubleshooting checklist I can work through step by step."
        ),
        icon="/public/debug.svg",
    ),
]


@cl.set_starters
async def set_starters():
    return HPC_STARTERS
