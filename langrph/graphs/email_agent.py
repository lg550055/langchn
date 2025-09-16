import time
from chains.notice_extraction import NoticeEmailExtract
from graphs.notice_extraction import NOTICE_EXTRACTION_GRAPH, GraphState
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode
from utils.logging_config import LOGGER


@tool
def forward_email(email_message: str, send_to_email: str) -> bool:
    """
    Simulates Forward an email_message to the address of send_to_email.
    Returns true.
    """
    LOGGER.info(f"Forwarding the email to {send_to_email}...")
    time.sleep(2)
    LOGGER.info("Email forwarded!")
    return True


@tool
def send_wrong_email_notification_to_sender(
    sender_email: str, correct_department: str
):
    """
    Simulates send an email back to the sender informing them that
    they have the wrong address. The email should be sent
    to the correct_department.
    """
    LOGGER.info(f"Sending wrong email notification to {sender_email}...")
    time.sleep(2)
    LOGGER.info("Email sent!")
    return True


@tool
def extract_notice_data(
    email: str, escalation_criteria: str
) -> NoticeEmailExtract:
    """
    Extract structured fields from a regulatory notice.
    This should be used when the email message comes from
    a regulatory body or auditor regarding a property or
    construction site that the company works on.

    escalation_criteria is a description of which kinds of
    notices require immediate escalation.

    After calling this tool, you don't need to call any others.
    """
    LOGGER.info("Calling the email notice extraction graph...")
    initial_state = {
        "notice_message": email,
        "notice_email_extract": None,
        "critical_fields_missing": False,  # IGNORE
        "escalation_text_criteria": escalation_criteria,
        "escalation_dollar_criteria": 100_000,
        "requires_escalation": False,
        "escalation_emails": ["brog@abc.com", "bigceo@company.com"],
    }

    results = NOTICE_EXTRACTION_GRAPH.invoke(GraphState(**initial_state))
    return results["notice_email_extract"]


@tool
def determine_email_action(email: str) -> str:
    """
    Call to determine which action should be taken
    for an email. Only use when the other tools don't seem
    relevant for the email task. Do not call this tool if
    you've already called extract_notice_data.
    """
    return """
    If the email appears to be an invoice of any kind or related to
    billing, forward the email to the billing and invoices team:
    billing@company.com and send a wrong email notice back to the
    sender. The correct department is billing@company.com.

    If the email appears to be from a customer, forward to
    support@company.com, cdetuma@company.com, and ctu@abc.com.
    Be sure to forward it to all three emails listed.
    Send a wrong email notice back to the
    customer and let them know the correct department is
    support@company.com.

    For any other emails, please send a wrong email notification
    and try to infer the correct department from one of
    billing@company.com, support@company.com,
    humanresources@company.com, and it@company.com.
    """
