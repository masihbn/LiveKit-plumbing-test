import os
import sys

from database import prompts, WorkersTable
from models import UserData, ServiceType

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from typing import Annotated, Optional
from dataclasses import fields

from dotenv import load_dotenv
from pydantic import Field

from livekit.agents import (
    Agent,
    AgentSession,
    AudioConfig,
    BackgroundAudioPlayer,
    FunctionTool,
    JobContext,
    RunContext,
    ToolError,
    WorkerOptions,
    cli,
    function_tool,
)
from livekit.plugins import cartesia, deepgram, openai, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

load_dotenv(override=True)


RunContext_T = RunContext[UserData]


class VoiceAgent(Agent):
    def __init__(self) -> None: super().__init__(instructions=prompts['greetings'])

    @property
    def tools(self): return [self.update_user_info, self.convince_user, self.update_reason_of_call, self.final_double_check]

    @function_tool()
    async def update_user_info(
            self,
            name: Annotated[Optional[str], Field(description="The customer's name")] = None,
            number: Annotated[Optional[str], Field(description="The customer's phone number")] = None,
            address: Annotated[Optional[str], Field(description="The customer's address")] = None,
            postal_code: Annotated[Optional[str], Field(description="The customer's postal code")] = None,
            context: RunContext[UserData] = None,
    ) -> str:
        f"""
        Called when the user provides *any* of these contact details: {', '.join(f.name for f in fields(UserData))}.
        Before calling this function, confirm the provided values with the user.
        """
        if not any([name, number, address, postal_code]):
            return "No fields provided to update."

        userdata = context.userdata
        updated = []

        if name is not None:
            userdata.name = name
            updated.append(("name", name))

        if number is not None:
            userdata.phone_number = number
            updated.append(("phone number", number))

        if address is not None:
            userdata.address = address
            updated.append(("address", address))

        if postal_code is not None:
            userdata.postal_code = postal_code
            updated.append(("postal code", postal_code))

        return f'Updated: {', '.join(f"{label} to {value}" for label, value in updated) if updated else 'Nothing'}'

    @function_tool()
    async def convince_user(
            self,
            context: RunContext[UserData] = None,
    ) -> str:
        """
        Called when the user refuses to provide ANY information.
        MAKE SURE YOU GET THE INFORMATION.
        """
        return "All the information is needed to ensure our agents can reach you. Without the information, I can't set the appointment"

    @function_tool()
    async def update_reason_of_call(
            self,
            reason: Annotated[str, Field(description="The reason for the call - must be one of: Plumbing, Pest Control, or Roofing Issues")],
            context: RunContext[UserData],
    ) -> str:
        f"""Called when the user provides their reason for the call.
        Only accepts: {', '.join(service.value for service in ServiceType)}."""
        userdata = context.userdata
        if userdata.set_reason_of_call(reason):
            return f"The reason for call is updated to {reason}"
        else:
            return f"Invalid reason. Please choose one of: {', '.join([service.value for service in ServiceType])}"

    @function_tool()
    async def final_double_check(
            self,
            context: RunContext[UserData],
    ) -> str:
        f"""
        Called at the end of the conversation to finalize the appointment and DOUBLE-CHECK the information with the user.
        Repeat all the information received from the user and update anything that's wrong.
        """
        userdata = context.userdata
        summary = userdata.summarize()
        return f"Let me confirm the information I have: {[f'{k}: {v}' for k, v in summary.items()]}"


async def entrypoint(ctx: JobContext):
    await ctx.connect()

    userdata = UserData()
    session = AgentSession[UserData](
        userdata=userdata,
        stt=deepgram.STT(model="nova-3"),
        llm=openai.LLM(model="gpt-4o", parallel_tool_calls=False, temperature=0.45),
        tts=cartesia.TTS(voice="f786b574-daa5-4673-aa0c-cbe3e8534c02", speed="fast"),
        turn_detection=MultilingualModel(),
        vad=silero.VAD.load(),
        max_tool_steps=10,
    )

    await session.start(agent=VoiceAgent(), room=ctx.room)


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
