import os
import sys

from database import prompts, WorkersTable
from models import UserData, ServiceType

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from typing import Annotated, Optional, Literal
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
    def __init__(self) -> None:
        super().__init__(instructions=prompts['greetings'])
        self.service_type = None

    @property
    def tools(self):
        base_tools = [self.update_user_info, self.convince_user, self.update_reason_of_call, self.get_available_times, self.final_double_check]
        
        if self.service_type:
            base_tools.append(self.build_set_appointment_tool(self.service_type))
        
        return base_tools

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
        service_type = userdata.set_reason_of_call(reason)
        if service_type:
            self.service_type = service_type
            return f"The reason for call is updated to {reason}. Now I can help you book an appointment. What time would you prefer?"
        else:
            return f"Invalid reason. Please choose one of: {', '.join([service.value for service in ServiceType])}"

    @function_tool()
    async def get_available_times(
            self,
            context: RunContext[UserData],
    ) -> str:
        """
        Called when the user has provided all the information and ready to set the time for the appointment.
        """
        if not self.service_type:
            return f"Please first tell me what type of service you need {', '.join(i.value for i in ServiceType)} so I can show you available times."

        available_times = WorkersTable.get_all_availabilities(self.service_type)
        if not available_times:
            return f"Sorry, there are no available appointments for {self.service_type.value} at the moment. Please try again later."
        
        time_strings = [f"{slot[0].strftime('%Y-%m-%d')} at {slot[1].strftime('%H:%M')}" for slot in available_times]
        return f"Here are the available times for {self.service_type.value}: {', '.join(time_strings)}. Which time works best for you?"

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

    def build_set_appointment_tool(
        self,
        service_type: ServiceType,
    ) -> FunctionTool:
        if not service_type:
            raise ToolError("Please specify the type of service you're looking for")

        available_times = WorkersTable.get_all_availabilities(service_type)
        available_time_strings = [f"{slot[0].strftime('%Y-%m-%d')} at {slot[1].strftime('%H:%M')}" for slot in available_times]

        @function_tool
        async def set_appointment_time(
            context: RunContext[UserData],
            appointment_time: Annotated[
                str,
                Field(
                    description="The appointment time the user selected.",
                    json_schema_extra={"enum": available_time_strings},
                ),
            ],
        ) -> str:
            """
            Call this when the user selects an appointment time from the available slots.
            The user must provide clear and specific input. For example, they might say:
            - "I'd like to book for 2025-08-21 at 16:00"
            - "Can I get the 10:00 slot on August 22nd?"
            - "I'll take the 17:00 appointment"
            """
            selected_slot = None
            for slot in available_times:
                slot_string = f"{slot[0].strftime('%Y-%m-%d')} at {slot[1].strftime('%H:%M')}"
                if slot_string == appointment_time:
                    selected_slot = slot
                    break
            
            if not selected_slot:
                raise ToolError(f"error: {appointment_time} was not found in available times.")

            worker = WorkersTable.get_next_free_worker(selected_slot)
            if not worker:
                raise ToolError(f"error: No worker available for {appointment_time}")

            context.userdata.appointment_time = appointment_time
            return f"Perfect! I've scheduled your {service_type.value} appointment for {appointment_time}. Your assigned worker will be {worker.name}."

        return set_appointment_time


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
