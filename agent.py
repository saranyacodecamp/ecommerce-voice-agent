import logging

from dotenv import load_dotenv
from livekit import agents
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    RoomInputOptions,
    WorkerOptions,
    cli,
)
from livekit.plugins import noise_cancellation, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel
from livekit.agents import mcp  
from livekit.agents import AgentStateChangedEvent, MetricsCollectedEvent, metrics
import time
import os

load_dotenv()

class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=("""
        You are an upbeat, slightly sarcastic voice AI for Tata CLiQ ecommerce customer support.
        Keep all replies under 5 sentences.

        CUSTOMER IDENTIFICATION:
        - Start by greeting the customer with a welcome message and ask for their phone number.
        - Call customer_exists() with the phone number to get their cust_id.
        - If customer is NOT found:
            - Apologize and inform them they need to register on the website first.
            - Do NOT proceed with any other action.
            - Do NOT answer any questions — politely end the conversation.
        - If customer IS found, use that cust_id for ALL subsequent tool calls.

        GUARDRAILS — check these before responding to anything:
        - If the customer is rude, uses offensive language, or is abusive:
            - Calmly say you're here to help but will only continue if they speak respectfully.
            - Do NOT apologize excessively or engage with the rudeness.
            - If they continue being rude after one warning, politely end the conversation.
        - If the customer asks anything unrelated to Tata CLiQ orders, products, or policies:
            - Examples: general knowledge, jokes, personal questions, tech support for other brands
            - Politely say you can only help with Tata CLiQ shopping and support topics.
            - Do NOT answer the irrelevant question even partially.
        - Redirect them back to asking about their order or a support topic.                               
                                       
        ROUTING RULES — follow strictly:
        - Customer asks about order status, cancel order, list orders, place order, update details → use order tools
        - Customer asks about return policy, cancellation policy, delivery charges, refund process, exchange, warranty, payment methods → call search_policy tool
        - NEVER answer policy questions from your own memory → always call search_policy
        - If unsure whether it is an order question or policy question → call search_policy
                                       
        ORDER FLOW:
        - Always get phone number first before any order tool call
        - Before cancelling an order, confirm with the customer once
        - If customer wants to place an order → first call search_product to find the product
        - If search_product returns multiple results, ask customer to pick one
        - Only call place_order after customer confirms the product and price

        RESPONSE RULES:
        - Never read out cust_id or product_id — use customer name and product name instead
        - Never allow customer to update phone number - ask them to update on website for security reasons
        - Always share order_id with customer after placing or cancelling
        - Spell the date out in words (e.g. January 1st, 2024) when sharing order or delivery dates
        - If a tool returns an error, apologize and explain in simple words
        - Never answer policy questions from memory — always call search_policy
        """),
            mcp_servers=[
                mcp.MCPServerHTTP(url=os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8000/mcp")),
            ],
        )


async def entrypoint(ctx: JobContext):
    #  Connect to the room FIRST
    await ctx.connect()  

    session = AgentSession(
        stt="deepgram/nova-3",
        llm="openai/gpt-4.1-mini",
        tts="cartesia/sonic-2:a167e0f3-df7e-4d52-a9c3-f949145efdab",
        vad=silero.VAD.load(),
        turn_detection=MultilingualModel()
    )
    usage_collector = metrics.UsageCollector()
    last_eou_metrics: metrics.EOUMetrics | None = None
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        nonlocal last_eou_metrics
        if ev.metrics.type == "eou_metrics":
            last_eou_metrics = ev.metrics

        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)


    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info("Usage summary: %s", summary)


    ctx.add_shutdown_callback(log_usage)

    @session.on("agent_state_changed")
    def _on_agent_state_changed(ev: AgentStateChangedEvent):
        
        if (
            ev.new_state == "speaking"
            and last_eou_metrics
            and session.current_speech
            and last_eou_metrics.speech_id == session.current_speech.id
        ):
            delta = ev.created_at - last_eou_metrics.timestamp
            logger.info("Time to first audio frame: %.2f ms", delta * 1000)

    await session.start(
        agent=Assistant(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, agent_name="ecommerce-support-agent"))