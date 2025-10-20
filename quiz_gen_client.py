import asyncio

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from fastmcp.tools import Tool
import argparse

async def quiz_generation_client(pdf_file_dir: str = "/workspace/test_upload/", save_csv_dir: str ='/workspace/mnt/'):
    """Run the quiz generation pipeline and return its textual output.

    Keeps the client connected for the duration of the call using the async context manager.
    """
    client = Client(transport=StreamableHttpTransport("http://localhost:4777/mcp"))
    async with client:
        # list available tools (debugging) -- optional
        try:
            tools: list[Tool] = await client.list_tools()
            for tool in tools:
                print(f"Tool: {tool}")
        except Exception:
            # non-fatal: continue to call the pipeline even if listing fails
            pass

        # call the quiz generation pipeline while the client is still connected
        call_payload = {"pdf_file_dir": pdf_file_dir, "save_csv_dir": save_csv_dir}
        result = await client.call_tool("quiz_generating_pipeline", call_payload)
        # result may be an object with .content; guard access
        try:
            text = result.content[0].text
        except Exception:
            # fallback to str(result)
            text = str(result)

        print(f"bash result: {text}")
        # return the textual result so callers can pipe it into downstream tasks
        return text
        #result = await client.call_tool("tavily_concurrent_search_async", {"search_queries": ["Who is Leonardo Da Vinci?","what is the difference between CPU and GPU?"], "tavily_topic":"general","tavily_days":1})
        #print(type(result))
        #print(f" ---- \n result: \n\n {result} ----")
        


if __name__ == "__main__":
    argparser = argparse.ArgumentParser(description="Quiz Generation Client")
    argparser.add_argument(
        "--pdf_file_dir",
        type=str,
        default="/workspace/test_upload/",
        help="The directory containing PDF files for quiz generation.",
    )
    argparser.add_argument(
        "--save_csv_dir",
        type=str,
        default="/workspace/mnt/",
        help="The directory to save generated CSV files.",
    )
    args = argparser.parse_args()   
    pdf_file_dir=args.pdf_file_dir
    save_csv_dir=args.save_csv_dir
    
    asyncio.run(quiz_generation_client(pdf_file_dir=pdf_file_dir, save_csv_dir=save_csv_dir))
