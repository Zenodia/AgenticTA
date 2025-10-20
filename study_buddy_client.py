import asyncio

import httpx

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from colorama import Fore
import argparse
async def study_buddy_client_requests(query: str = ""):
    httpx_client = httpx.AsyncClient()

    def httpx_client_factory(
        headers: dict[str, str],
        timeout: httpx.Timeout | None = None,
        auth: httpx.Auth | None = None,
    ):
        httpx_client.headers = headers
        if timeout:
            httpx_client.timeout = timeout
        if auth:
            httpx_client.auth = auth
        return httpx_client

    async with Client(
        transport=StreamableHttpTransport(
            "http://localhost:4100/mcp",
            httpx_client_factory=httpx_client_factory,
        )
    ) as client:
        httpx_client.headers["x-forwarded-access-token"] = "TOKEN_1"
        # Request 1
        #query="someone who has a good sense of humor, and can make funny joke out of the boring subject I'd studying"
        result1 = await client.call_tool("study_buddy_response", {"query": query})
        print("---"*15)        
        print(Fore.CYAN + f"Request 1 result: {result1.content[0].text}" , Fore.RESET) 
        print("\n"*3)
        #query="help me solve this:The circumference of a circle is 30. What is its area?"
        # the subsequent request within the same session, but the token should be updated by the reverse proxy
        #result2 = await client.call_tool("study_buddy_response", {"query": query})
        #print("---"*15)
        #print(Fore.CYAN +f"Request 2 result: {result2.content[0].text}", Fore.RESET) 
        #print("\n"*3)
        #query="teach me how to solve this equation  4x-3=5x+1"
        # the subsequent request within the same session, but the token should be updated by the reverse proxy
        #result3 = await client.call_tool("study_buddy_response", {"query": query})
        #print("---"*15)
        #print(Fore.CYAN + f"Request 3 result: {result3.content[0].text}", Fore.RESET)
        output=result1.content[0].text
        return output
if __name__ == "__main__":
    argparser = argparse.ArgumentParser(description="Study Buddy Client")
    argparser.add_argument(
        "--query",
        type=str,
        default="",
        help="The query to send to the study buddy.",
    )
    args = argparser.parse_args()
    query=args.query
    output= asyncio.run(study_buddy_client_requests(query=query))
