import asyncio
from pipeline.reader import read_md_files
from graph.state import PPTState


async def node_file_parser(state: PPTState) -> dict:
    md_content = await asyncio.to_thread(read_md_files, state["folder"])
    return {"md_content": md_content}
