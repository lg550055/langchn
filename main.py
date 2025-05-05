import re
import json
from dotenv import load_dotenv
# from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
from tools import search_tool

load_dotenv()

llm = ChatOpenAI(model="gpt-4o-mini")
# response = llm.invoke("In a few words, what is the fwd pe ratio?")
# print(response)

# prompt = "You are a smart assistant that can search the web to fetch current metrics."
prompt = ChatPromptTemplate.from_messages([
    ("system", """
    You are a smart assistant that searches the web to fetch current data.
    Respond in the format below and don't include any other information:
    1. Closing Price: <closing_price> as a number without $ or commas
    2. Closing Price Date: <closing_price_date> in YYYYMMDD format
    3. FY 2026 EPS Estimate: <eps_estimate> as a number without $ or commas
    """
    ),
    ("placeholder", "{chat_history}"),
    ("human", "{query}"),
    ("placeholder", "{agent_scratchpad}"),
])

agent = create_tool_calling_agent(
    llm=llm,
    tools=[search_tool],
    prompt=prompt,
)

agent_executor = AgentExecutor(
    agent=agent,
    tools=[search_tool],
    verbose=True,
)

ticker = input("Enter the stock ticker: ")
raw_response = agent_executor.invoke({"query": f"For {ticker}, what is the most recent closing price and estimated eps for the year 2026?"})

# Extract the closing price, closing date and fy 2026 eps estimate into a json object
response = raw_response['output']
print(response)
closing_price = re.search(r"Closing Price: (.+)", response).group(1)
closing_price_date = re.search(r"Closing Price Date: (.+)", response).group(1)
eps_estimate = re.search(r"FY 2026 EPS Estimate: (.+)", response).group(1)

# Parse the closing price and eps estimate to float
closing_price = float(closing_price)
eps_estimate = float(eps_estimate)
# Remove '/' from closing price date
# closing_price_date = closing_price_date.replace("/", "")


# Create a json object with the closing price, closing date and fy 2026 eps estimate
json_object = {
    "ticker": ticker,
    "closing_price": closing_price,
    "closing_price_date": closing_price_date,
    "eps_estimate": eps_estimate,
    "fwd_pe": round(closing_price / eps_estimate, 1)
}

# Save the json object to a file
with open(f"{ticker}_{closing_price_date}.json", "w") as outfile:
    json.dump(json_object, outfile, indent=4)
