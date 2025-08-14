import os
import sys

from database import prompts, WorkersTable
from models import UserData, ServiceType

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from typing import Annotated, Literal

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
    def __init__(self) -> None:
        super().__init__(
            instructions=prompts['greetings'],
        )

    @property
    def tools(self):
        return [
            self.update_name, self.update_phone_number, self.update_address_and_postal_code,
            self.update_reason_of_call, self.final_double_check
        ]

    @function_tool()
    async def update_name(
            self,
            name: Annotated[str, Field(description="The customer's name")],
            context: RunContext[UserData],
    ) -> str:
        """Called when the user provides their name.
        Confirm the spelling with the user before calling the function.
        If user refuses to provide this, say that you can't set an appointment without this info"""
        userdata = context.userdata
        userdata.name = name
        return f"The name is updated to {name}"

    @function_tool()
    async def update_phone_number(
            self,
            number: Annotated[str, Field(description="The customer's phone number")],
            context: RunContext[UserData],
    ) -> str:
        """Called when the user provides their phone number.
        Confirm the phone number with the user before calling the function.
        If user refuses to provide this, say that you can't set an appointment without this info"""
        userdata = context.userdata
        userdata.phone_number = number
        return f"The phone number is updated to {number}"

    @function_tool()
    async def update_address_and_postal_code(
            self,
            address: Annotated[str, Field(description="The customer's address")],
            postal_code: Annotated[str, Field(description="The customer's postal code")],
            context: RunContext[UserData],
    ) -> str:
        """Called when the user provides their address.
        Confirm the address with the user before calling the function.
        If user refuses to provide this, say that you can't set an appointment without this info"""
        userdata = context.userdata
        userdata.address = address
        userdata.postal_code = postal_code
        return f"The address is updated to {address} and postal code to {postal_code}"

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
        """Called when the user has provided all the details and to double-check the information with the user.
        Repeat all the information received from the user and update anything that's wrong.
        If you've already doubled-checked once, and just made a change to a few of the information, then just double-check the changed ones"""
        userdata = context.userdata
        summary = userdata.summarize()
        return f"Let me confirm the information I have: {[f'{k}: {v}' for k, v in summary.items()]}\n  Please confirm if this information is correct or let me know what needs to be updated."

    # def build_combo_order_tool(
    #     self, combo_items: list[MenuItem], drink_items: list[MenuItem], sauce_items: list[MenuItem]
    # ) -> FunctionTool:
    #     available_times = WorkersTable.get_all_availabilities(ServiceType.PEST_CONTROL)
    #
    #     @function_tool
    #     async def order_combo_meal(
    #         ctx: RunContext[UserData]
    #     ):
    #         """This is called after all the information has been collected from the user."""
    #
    #     return None


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
