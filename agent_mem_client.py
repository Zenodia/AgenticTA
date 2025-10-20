import asyncio
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from fastmcp.tools import Tool
from colorama import Fore
import ast 
import argparse
async def agentic_mem_mcp_client(query, user_id):
    client = Client(transport=StreamableHttpTransport("http://localhost:4327/mcp"))  # use /mcp path
    async with client:
        tools: list[Tool] = await client.list_tools()
        #for tool in tools:
            #print(f"Tool: {tool}")
        #input= "hi, my name is Babe, I am a pig and I can talk, my best friend is a chicken named Rob." #"I had a fight with Rob, he ruined my birthday, he is no longer my best friend !"
        result = await client.call_tool(
            "memory_agent",
            {
                "query": query ,
                "user_id": user_id
            }
        )
        """
        result = await client.call_tool(
            "fetch_memory_items",
            {
                "query": query ,
                "user_id": user_id
            }
        )"""
        #print(Fore.GREEN +"fetch_memory_items result type ", type(result), result, Fore.RESET)
        output=result.content[0].text
        #output=ast.literal_eval(output)
        #print(Fore.GREEN +"fetch_memory_items result type ", type(output), output, Fore.RESET)
     # mcp response to text , which a list with TextContent in the list, access the text via attribute 
    ## example below 
    ### CallToolResult(content=[TextContent(type='text', text="That's quite an interesting introduction, Babe the talking pig! I'm excited to meet you and your feathered friend, Rob the chicken. What kind of adventures do you two like to have on the farm?", annotations=None, meta=None)], structured_content={'result': "That's quite an interesting introduction, Babe the talking pig! I'm excited to meet you and your feathered friend, Rob the chicken. What kind of adventures do you two like to have on the farm?"}, data="That's quite an interesting introduction, Babe the talking pig! I'm excited to meet you and your feathered friend, Rob the chicken. What kind of adventures do you two like to have on the farm?", is_error=False)
    
    #print(Fore.CYAN + "inside mcp client , the respond from memory enabled agent:\n", output, Fore.RESET)
    return output
if __name__ == "__main__":
    argparser = argparse.ArgumentParser(description="Agentic Memory MCP Client")
    argparser.add_argument(
        "--query",
        type=str,
        default="",
        help="The query to send to the agentic memory MCP.",
    )
    argparse.add_argument(
        "--user_id",
        type=str,
        default="user",
        help="The user ID for the memory agent.",
    )
    args= argparser.parse_args()
    query=args.query 
    user_id=args.user_id
    output = asyncio.run(agentic_mem_mcp_client(query, user_id))
    print("\n\n\n")
    print(Fore.GREEN +"output from main ", type(output), output, Fore.RESET)

