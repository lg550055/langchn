from langchain_community.tools import DuckDuckGoSearchRun
from langchain.tools import Tool

search = DuckDuckGoSearchRun()
search_tool = Tool(
    name="search",
    func=search.run,
    description="Search the web using DuckDuckGo"
)
