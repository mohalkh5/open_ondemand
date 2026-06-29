"""Generic coding conversation starters for the Chainlit welcome screen."""

import chainlit as cl

CODING_STARTERS = [
    cl.Starter(
        label="Explain a concept",
        message=(
            "Explain recursion in plain language with a simple example. "
            "Keep it conceptual and avoid assuming any specific tools or environment."
        ),
        icon="/public/learn.svg",
    ),
    cl.Starter(
        label="Plan a small project",
        message=(
            "Help me plan the structure for a small Python command-line tool. "
            "Suggest a simple layout for source files, tests, and dependencies."
        ),
        icon="/public/workflow.svg",
    ),
    cl.Starter(
        label="Python best practices",
        message=(
            "What are good general practices for organizing a Python project? "
            "Cover virtual environments, dependency management, and basic testing."
        ),
        icon="/public/terminal.svg",
    ),
    cl.Starter(
        label="Debug step by step",
        message=(
            "My program is failing with an error I do not understand. "
            "Walk me through a practical debugging checklist I can follow step by step."
        ),
        icon="/public/debug.svg",
    ),
]


@cl.set_starters
async def set_starters():
    return CODING_STARTERS
