from typing import TypedDict
from chains.escalation_check import ESCALATION_CHECK_CHAIN
from chains.notice_extraction import NOTICE_PARSER_CHAIN, NoticeEmailExtract
from langgraph.graph import END, START, StateGraph
from pydantic import EmailStr
from utils.graph_utils import create_legal_ticket, send_escalation_email
from utils.logging_config import LOGGER


class GraphState(TypedDict):
    notice_message: str
    notice_email_extract: NoticeEmailExtract | None
    escalation_text_criteria: str
    escalation_dollar_criteria: float
    requires_escalation: bool
    escalation_emails: list[EmailStr] | None
    follow_ups: dict[str, bool] | None
    current_follow_up: str | None


workflow = StateGraph(GraphState)


def parse_notice_message_node(state: GraphState) -> GraphState:
    """Use the notice parser chain to extract fields from the notice"""
    LOGGER.info("Parsing notice...")
    raw = NOTICE_PARSER_CHAIN.invoke({"message": state["notice_message"]})

    # Coerce the chain output into the Pydantic model so downstream code
    # can rely on attribute access and typed fields.
    try:
        if isinstance(raw, NoticeEmailExtract) or raw is None:
            notice_email_extract = raw
        elif isinstance(raw, dict):
            notice_email_extract = NoticeEmailExtract.model_validate(raw)
        else:
            # Try to coerce unknown objects (e.g., SimpleNamespace) via dict()
            notice_email_extract = None
            try:
                as_dict = dict(raw) if isinstance(raw, dict) else getattr(raw, "__dict__", None)
                if as_dict:
                    notice_email_extract = NoticeEmailExtract.model_validate(as_dict)
            except Exception:
                notice_email_extract = None

    except Exception:
        LOGGER.exception("Failed to coerce parser output to NoticeEmailExtract")
        notice_email_extract = None

    state["notice_email_extract"] = notice_email_extract
    return state


def check_escalation_status_node(state: GraphState) -> GraphState:
    """Determine whether a notice needs escalation"""
    LOGGER.info("Determining escalation status...")
    esc_raw = ESCALATION_CHECK_CHAIN.invoke(
        {
            "escalation_criteria": state["escalation_text_criteria"],
            "message": state["notice_message"],
        }
    )

    try:
        text_check = bool(getattr(esc_raw, "needs_escalation", esc_raw.get("needs_escalation") if isinstance(esc_raw, dict) else False))
    except Exception:
        LOGGER.exception("Failed to read needs_escalation from escalation check result")
        text_check = False

    max_fine: float | None = None
    extract = state.get("notice_email_extract")
    if extract is not None:
        try:
            if not isinstance(extract, NoticeEmailExtract):
                # try coercing dict-like objects
                if isinstance(extract, dict):
                    extract = NoticeEmailExtract.model_validate(extract)
                    state["notice_email_extract"] = extract
                else:
                    # leave as-is if we can't coerce
                    pass
            max_fine = getattr(extract, "max_potential_fine", None)
        except Exception:
            LOGGER.exception("Failed to read max_potential_fine from notice_email_extract")
            max_fine = None

    if text_check or (max_fine is not None and max_fine >= state["escalation_dollar_criteria"]):
        state["requires_escalation"] = True
    else:
        state["requires_escalation"] = False

    return state


def send_escalation_email_node(state: GraphState) -> GraphState:
    """Send an escalation email"""
    if state["notice_email_extract"] and state["escalation_emails"]:
        send_escalation_email(
            notice_email_extract=state["notice_email_extract"],
            escalation_emails=state["escalation_emails"],
        )
    else:
        LOGGER.warning(
            "Skipped escalation email: missing notice_email_extract or escalation_emails"
        )

    return state


def create_legal_ticket_node(state: GraphState) -> GraphState:
    """Node to create a legal ticket"""
    if state["notice_email_extract"]:
        follow_up = create_legal_ticket(
            current_follow_ups=state.get("follow_ups"),
            notice_email_extract=state["notice_email_extract"],
        )
        state["current_follow_up"] = follow_up
    else:
        LOGGER.warning("Skipping ticket creation: missing notice_email_extract")

    return state


def route_escalation_status_edge(state: GraphState) -> str:
    """Determine whether to send an escalation email or
    create a legal ticket"""
    if state["requires_escalation"]:
        LOGGER.info("Escalation needed!")
        return "send_escalation_email"

    LOGGER.info("No escalation needed")
    return "create_legal_ticket"


workflow.add_node("parse_notice_message", parse_notice_message_node)
workflow.add_node("check_escalation_status", check_escalation_status_node)
workflow.add_node("send_escalation_email", send_escalation_email_node)
workflow.add_node("create_legal_ticket", create_legal_ticket_node)

workflow.add_edge(START, "parse_notice_message")
workflow.add_edge("parse_notice_message", "check_escalation_status")
workflow.add_conditional_edges(
    "check_escalation_status",
    route_escalation_status_edge,
    {
        "send_escalation_email": "send_escalation_email",
        "create_legal_ticket": "create_legal_ticket",
    },
)
workflow.add_edge("send_escalation_email", "create_legal_ticket")
workflow.add_edge("create_legal_ticket", END)

NOTICE_EXTRACTION_GRAPH = workflow.compile()
